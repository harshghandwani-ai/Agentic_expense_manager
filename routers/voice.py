"""
routers/voice.py -- WebSocket endpoint for real-time STT.
"""
import os
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

API_KEY = os.getenv("DEEPGRAM_API_KEY")

@router.websocket("/transcribe")
async def transcribe_audio(websocket: WebSocket):
    """
    WebSocket endpoint for real-time Speech-to-Text.
    Expects binary audio data (linear16, 16kHz, Mono).
    Returns JSON transcripts.
    """
    await websocket.accept()
    
    if not API_KEY:
        logger.error("DEEPGRAM_API_KEY is not set.")
        await websocket.close(code=1011)
        return

    client = DeepgramClient(API_KEY)
    dg_connection = client.listen.websocket.v("1")

    # Access current event loop to use in callbacks if they are sync
    loop = asyncio.get_event_loop()

    # Callback for transcripts
    def on_message(self, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if len(transcript) > 0:
            # Send results back to the browser via the event loop
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({
                    "channel": "transcript",
                    "text": transcript,
                    "is_final": result.is_final
                }),
                loop
            )

    # Callback for silence detection
    def on_utterance_end(self, utterance_end, **kwargs):
        asyncio.run_coroutine_threadsafe(
            websocket.send_json({"channel": "utterance_end"}),
            loop
        )

    def on_error(self, error, **kwargs):
        logger.error(f"Deepgram Error: {error}")
        asyncio.run_coroutine_threadsafe(
            websocket.send_json({"channel": "error", "message": str(error)}),
            loop
        )

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    # Exact settings from voice.py
    options = LiveOptions(
        model="nova-2",
        language="en-IN",
        smart_format=True,
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        interim_results=True,
        utterance_end_ms=1000,
        vad_events=True,
        endpointing=300
    )

    if not dg_connection.start(options):
        logger.error("Failed to connect to Deepgram.")
        await websocket.close(code=1011)
        return

    try:
        while True:
            # Receive binary audio chunk from browser
            data = await websocket.receive_bytes()
            dg_connection.send(data)
    except WebSocketDisconnect:
        logger.info("Browser disconnected.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        dg_connection.finish()
        logger.info("Deepgram connection finished.")
