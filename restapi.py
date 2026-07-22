from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import torchaudio as ta
import torch
import os
import time
from chatterbox.tts_turbo import ChatterboxTurboTTS, Conditionals
from pathlib import Path
from typing import List, Dict
import uuid
import io
from threading import RLock

from voice_management import delete_voice_artifacts, normalize_voice_id


SERVICE_HOST = os.environ.get("CHATTERBOX_HOST", "0.0.0.0")
# Keep the code-level fallback on the released shared port. DwemerDistro writes
# .dwemerdistro-port for fresh installs and explicit migrations.
SERVICE_PORT = int(os.environ.get("CHATTERBOX_PORT", "8020"))

app = FastAPI(title="Chatterbox TTS API", version="0.1.0")

# Load model once at startup
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model = ChatterboxTurboTTS.from_pretrained(device=DEVICE)

VOICE_DIR = Path("voices")
VOICE_DIR.mkdir(exist_ok=True)
VOICE_LOCK = RLock()


# Pydantic models for request/response
class SynthesisRequest(BaseModel):
    text: str
    speaker_wav: str
    language: str
    exaggeration: float = 0.5
    repetition_penalty: float = 1.2
    min_p: float = 0.00
    top_p: float = 0.95
    cfg_weight: float = 0.0
    temperature: float = 0.8
    top_k: int = 1000


# ============= GET ENDPOINTS =============

@app.get("/speakers_list")
async def get_speakers_list():
    """Get list of available speaker names (simplified format)."""
    speaker_names = []
    
    if VOICE_DIR.exists():
        # Get all .wav files in the voices directory
        wav_files = list(VOICE_DIR.glob("*.wav"))
        
        for wav_file in wav_files:
            # Skip output files
            if "_out.wav" in wav_file.name:
                continue
                
            voice_id = wav_file.stem  # filename without extension
            speaker_names.append(voice_id)
    
    return speaker_names


@app.get("/speakers_list_extended")
async def get_speakers_list_extended():
    """Get detailed list of available speaker voice files."""
    speakers = []
    
    if VOICE_DIR.exists():
        # Get all .wav files in the voices directory
        wav_files = list(VOICE_DIR.glob("*.wav"))
        
        for wav_file in wav_files:
            # Skip output files
            if "_out.wav" in wav_file.name:
                continue
                
            voice_id = wav_file.stem  # filename without extension
            cond_file = VOICE_DIR / f"{voice_id}.pt"
            
            speakers.append({
                "voice_id": voice_id,
                "wav_file": wav_file.name,
                "has_conditionals": cond_file.exists(),
                "can_delete": True,
                "source": "uploaded_sample",
            })
    
    return {"speakers": speakers, "count": len(speakers)}


@app.get("/speakers")
async def get_speakers_alt():
    """Alternative endpoint to get list of available speakers."""
    return await get_speakers_list()


@app.get("/sample/{file_name}")
async def get_sample(file_name: str):
    """Get a speaker sample audio file."""
    file_path = VOICE_DIR / file_name
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample file '{file_name}' not found")
    
    if not file_path.suffix == ".wav":
        raise HTTPException(status_code=400, detail="Only .wav files are supported")
    
    return FileResponse(file_path, media_type="audio/wav", filename=file_name)


# ============= POST ENDPOINTS =============

@app.post("/upload_sample")
async def upload_sample(
    wavFile: UploadFile = File(...),
    force: bool = Form(default=False),
):
    """Upload a voice sample to be used as a speaker reference."""
    start_time = time.time()
    
    # Validate file type
    if not wavFile.filename or not wavFile.filename.lower().endswith('.wav'):
        raise HTTPException(status_code=400, detail="Only .wav files are supported")

    try:
        voice_id = normalize_voice_id(wavFile.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    wav_path = VOICE_DIR / f"{voice_id}.wav"
    cond_path = VOICE_DIR / f"{voice_id}.pt"

    content = await wavFile.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded WAV is empty")

    temp_token = uuid.uuid4().hex
    temp_wav_path = VOICE_DIR / f".upload-{temp_token}.wav"
    temp_cond_path = VOICE_DIR / f".upload-{temp_token}.pt"
    backup_wav_path = VOICE_DIR / f".backup-{temp_token}.wav"
    backup_cond_path = VOICE_DIR / f".backup-{temp_token}.pt"
    replaced = False

    try:
        with VOICE_LOCK:
            replaced = wav_path.exists()
            if replaced and not force:
                raise HTTPException(
                    status_code=409,
                    detail=f"Voice '{voice_id}' already exists. Set force=true to replace it.",
                )

            temp_wav_path.write_bytes(content)
            cond_start = time.time()
            model.prepare_conditionals(str(temp_wav_path))
            cond_time = time.time() - cond_start
            model.conds.save(temp_cond_path)
            wav_backed_up = False
            cond_backed_up = False
            wav_installed = False
            cond_installed = False
            try:
                if wav_path.exists():
                    os.replace(wav_path, backup_wav_path)
                    wav_backed_up = True
                if cond_path.exists():
                    os.replace(cond_path, backup_cond_path)
                    cond_backed_up = True
                os.replace(temp_wav_path, wav_path)
                wav_installed = True
                os.replace(temp_cond_path, cond_path)
                cond_installed = True
            except Exception:
                if wav_installed and wav_path.exists():
                    wav_path.unlink()
                if cond_installed and cond_path.exists():
                    cond_path.unlink()
                if wav_backed_up and backup_wav_path.exists():
                    os.replace(backup_wav_path, wav_path)
                if cond_backed_up and backup_cond_path.exists():
                    os.replace(backup_cond_path, cond_path)
                raise
            backup_wav_path.unlink(missing_ok=True)
            backup_cond_path.unlink(missing_ok=True)

        total_time = time.time() - start_time
        
        print(f"[VOICE UPLOAD] voice_id={voice_id}, filename={wavFile.filename}")
        print(f"  - Conditional preparation: {cond_time:.3f}s")
        print(f"  - Total time: {total_time:.3f}s")

        return {
            "status": "success",
            "voice_id": voice_id,
            "wav_file": wav_path.name,
            "original_filename": wavFile.filename,
            "replaced": replaced,
            "inference_time": {
                "conditional_preparation": f"{cond_time:.3f}s",
                "total": f"{total_time:.3f}s"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")
    finally:
        for temp_path in (temp_wav_path, temp_cond_path):
            if temp_path.exists():
                temp_path.unlink()


@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    try:
        normalized = normalize_voice_id(voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with VOICE_LOCK:
        removed = delete_voice_artifacts(VOICE_DIR, normalized)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Voice '{normalized}' was not found")
    return {
        "status": "deleted",
        "voice_id": normalized,
        "removed": removed,
        "cache_invalidated": True,
    }


@app.post("/tts_to_audio/")
async def tts_to_audio(request: SynthesisRequest):
    """
    Generate TTS audio from text using a speaker voice.
    
    - **text**: The text to synthesize
    - **speaker_wav**: The voice ID or filename (without extension) of the speaker
    - **language**: Language code (currently not used by model but kept for API compatibility)
    - **exaggeration**: Emotion exaggeration level (default: 0.5)
    - **repetition_penalty**: Penalty for repetition (default: 1.2)
    - **min_p**: Minimum probability threshold (default: 0.0)
    - **top_p**: Top-p sampling threshold (default: 0.95)
    - **cfg_weight**: Classifier-free guidance weight (default: 0.0)
    - **temperature**: Sampling temperature (default: 0.8)
    - **top_k**: Top-k sampling (default: 1000)
    
    Note: CFG weight, min_p and exaggeration are not supported by Turbo version and will be ignored.
    """
    start_time = time.time()
    
    # Parse speaker_wav - could be voice_id or filename
    voice_id = request.speaker_wav
    if voice_id.endswith('.wav'):
        voice_id = voice_id[:-4]  # Remove .wav extension
    
    try:
        voice_id = normalize_voice_id(voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    wav_path = VOICE_DIR / f"{voice_id}.wav"

    try:
        with VOICE_LOCK:
            if not wav_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Voice audio file for '{voice_id}' not found"
                )

            # Prepare conditionals and generate while deletion/replacement is excluded.
            cond_start = time.time()
            model.prepare_conditionals(str(wav_path), exaggeration=request.exaggeration)
            cond_time = time.time() - cond_start

            gen_start = time.time()
            wav = model.generate(
                request.text,
                repetition_penalty=request.repetition_penalty,
                min_p=request.min_p,
                top_p=request.top_p,
                exaggeration=request.exaggeration,
                cfg_weight=request.cfg_weight,
                temperature=request.temperature,
                top_k=request.top_k
            )
            gen_time = time.time() - gen_start

        # Convert to bytes for streaming
        save_start = time.time()
        buffer = io.BytesIO()
        ta.save(buffer, wav, model.sr, format="wav")
        buffer.seek(0)
        save_time = time.time() - save_start

        total_time = time.time() - start_time
        
        print(f"[TTS GENERATION] voice_id={voice_id}, text_length={len(request.text)}, language={request.language}")
        print(f"  - Prepare conditionals: {cond_time:.3f}s")
        print(f"  - Generate audio: {gen_time:.3f}s")
        print(f"  - Prepare output: {save_time:.3f}s")
        print(f"  - Total time: {total_time:.3f}s")

        return StreamingResponse(
            buffer,
            media_type="audio/wav",
            headers={
                "X-Generation-Time": f"{gen_time:.3f}s",
                "X-Total-Time": f"{total_time:.3f}s"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")


# ============= HEALTH CHECK =============

@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "provider": "chatterbox",
        "runtime": "python",
        "api_family": "xtts-compatible",
        "port": SERVICE_PORT,
        "device": DEVICE,
        "model_loaded": model is not None,
        "voice_directory": str(VOICE_DIR)
    }


@app.get("/provider_info")
def provider_info():
    """Stable provider identity for DwemerDistro discovery UIs."""
    return health()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)
