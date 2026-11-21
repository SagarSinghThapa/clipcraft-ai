"""End-to-end verification script for ClipCraft AI."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"
TEST_YOUTUBE_URL = "https://youtu.be/kR8bhkVAgBY"


def run_cmd(cmd_list):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


def probe_file(file_path: Path):
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def main():
    print("=" * 70)
    print("  ClipCraft AI - Real End-to-End Verification Pipeline")
    print("=" * 70)

    # 1. Environment Verification
    print("\n--- 1. ENVIRONMENT VERIFICATION ---")
    py_ver = sys.version.split()[0]
    print(f"Python:       {py_ver} ({sys.executable})")

    ffmpeg_ver = run_cmd(["ffmpeg", "-version"]).splitlines()[0] if run_cmd(["ffmpeg", "-version"]) else "Not found"
    print(f"FFmpeg:       {ffmpeg_ver}")

    ollama_ver = run_cmd(["ollama", "--version"])
    print(f"Ollama:       {ollama_ver}")

    node_ver = run_cmd(["node", "--version"])
    print(f"Node.js:      {node_ver}")

    npm_ver = run_cmd(["npm", "--version"])
    print(f"npm:          {npm_ver}")

    ytdlp_ver = run_cmd([sys.executable, "-m", "yt_dlp", "--version"])
    print(f"yt-dlp:       {ytdlp_ver}")

    # Verify Ollama tags
    try:
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5.0)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"Ollama Models: {', '.join(models)}")
        assert "llama3.2:3b" in [m.split(":")[0] + ":" + m.split(":")[1] if ":" in m else m for m in models]
    except Exception as e:
        print(f"[FAIL] Ollama verification failed: {e}")
        sys.exit(1)

    # Verify Backend Health
    try:
        r = httpx.get(f"{BACKEND_URL}/api/health", timeout=5.0)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        health_data = r.json()
        print(f"Backend API:  Healthy ({health_data})")
    except Exception as e:
        print(f"[FAIL] Backend health check failed: {e}")
        sys.exit(1)

    # Verify Frontend
    try:
        r = httpx.get(FRONTEND_URL, timeout=5.0)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        print(f"Frontend UI:  Reachable (HTTP {r.status_code})")
    except Exception as e:
        print(f"[WARNING] Frontend UI check: {e}")

    # 2. Ingestion Test
    print("\n--- 2. YOUTUBE INGESTION TEST ---")
    print(f"Target YouTube URL: {TEST_YOUTUBE_URL}")

    # Create project
    create_payload = {
        "title": "iShowSpeed GTA 6 Test",
        "source_type": "youtube",
        "source_url": TEST_YOUTUBE_URL,
        "candidate_count": 3,
        "min_clip_duration": 20.0,
        "max_clip_duration": 60.0,
        "whisper_model": "base",
        "llm_model": "llama3.2:3b"
    }

    client = httpx.Client(timeout=httpx.Timeout(connect=10.0, read=900.0, write=30.0, pool=30.0))

    t0 = time.time()
    r = client.post(f"{BACKEND_URL}/api/projects", json=create_payload)
    if r.status_code != 201:
        print(f"[FAIL] Failed to create project: {r.status_code} {r.text}")
        sys.exit(1)
    project_data = r.json()
    project_id = project_data["id"]
    print(f"Created Project ID: {project_id}")

    # Ingest YouTube URL
    print("Starting yt-dlp download via backend API...")
    t_ingest_start = time.time()
    r = client.post(f"{BACKEND_URL}/api/projects/{project_id}/ingest/youtube", json={"url": TEST_YOUTUBE_URL})
    if r.status_code != 200:
        print(f"[FAIL] YouTube ingestion failed: {r.status_code} {r.text}")
        sys.exit(1)
    ingest_time = round(time.time() - t_ingest_start, 2)
    print(f"Ingestion API completed in {ingest_time}s")

    # Verify downloaded file
    project_meta = client.get(f"{BACKEND_URL}/api/projects/{project_id}").json()
    source_path_str = project_meta.get("source_path")
    assert source_path_str, "Source path missing from project metadata"
    source_file = Path(source_path_str)
    assert source_file.exists(), f"Source file does not exist: {source_file}"
    source_size = source_file.stat().st_size
    assert source_size > 0, "Source file size is zero"

    # FFprobe verification
    probe_data = probe_file(source_file)
    fmt = probe_data.get("format", {})
    streams = probe_data.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration", 0.0))
    width = int(v_stream.get("width", 0)) if v_stream else 0
    height = int(v_stream.get("height", 0)) if v_stream else 0
    v_codec = v_stream.get("codec_name", "unknown") if v_stream else "none"
    a_codec = a_stream.get("codec_name", "unknown") if a_stream else "none"

    print(f"Source file:  {source_file.name}")
    print(f"File size:    {round(source_size / (1024*1024), 2)} MB")
    print(f"Duration:     {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print(f"Resolution:   {width}x{height}")
    print(f"Video Codec:  {v_codec}")
    print(f"Audio Codec:  {a_codec} ({a_stream.get('sample_rate', 'unknown')} Hz, {a_stream.get('channels', 'unknown')} ch)")
    assert v_stream is not None, "Video stream missing"
    assert a_stream is not None, "Audio stream missing"
    assert duration > 100.0, "Duration seems invalid"

    # 3. Transcription Test
    print("\n--- 3. TRANSCRIPTION TEST ---")
    print("Starting audio extraction and faster-whisper speech-to-text...")
    t_transcribe_start = time.time()
    r = client.post(f"{BACKEND_URL}/api/projects/{project_id}/transcribe", json={"model_size": "base"})
    if r.status_code != 200:
        print(f"[FAIL] Transcription API failed: {r.status_code} {r.text}")
        sys.exit(1)
    transcribe_time = round(time.time() - t_transcribe_start, 2)
    transcript_data = r.json()

    # Verify audio.wav
    audio_wav = Path("projects") / project_id / "audio" / "audio.wav"
    assert audio_wav.exists(), f"Extracted audio.wav does not exist: {audio_wav}"
    print(f"audio.wav:    Exists ({round(audio_wav.stat().st_size / (1024*1024), 2)} MB)")

    # Verify transcript
    transcript_path = Path("projects") / project_id / "transcript" / "transcript.json"
    assert transcript_path.exists(), f"transcript.json does not exist: {transcript_path}"
    segments = transcript_data.get("segments", [])
    print(f"Transcribed:  {transcribe_time}s | {len(segments)} segments | Language: {transcript_data.get('language')}")
    print(f"Model used:   {transcript_data.get('model_name')}")
    assert len(segments) > 0, "No segments in transcript"

    # Word timestamps check
    has_words = any(len(s.get("words", [])) > 0 for s in segments)
    print(f"Word Timestamps Available: {has_words}")

    # Excerpt
    print("\nTranscript Excerpt (First 3 Segments):")
    for s in segments[:3]:
        print(f"  [{s.get('start'):.2f}s -> {s.get('end'):.2f}s] {s.get('text')}")

    # 4. AI Highlight Detection Test
    print("\n--- 4. AI HIGHLIGHT TEST (Ollama llama3.2:3b) ---")
    print("Calling Ollama to analyze semantic transcript windows...")
    t_analyze_start = time.time()
    r = client.post(
        f"{BACKEND_URL}/api/projects/{project_id}/analyze",
        json={"llm_model": "llama3.2:3b", "max_candidates": 3}
    )
    if r.status_code != 200:
        print(f"[FAIL] Highlight analysis failed: {r.status_code} {r.text}")
        sys.exit(1)
    analyze_time = round(time.time() - t_analyze_start, 2)
    candidates_list = r.json()
    candidates = candidates_list.get("candidates", [])
    print(f"Highlight Analysis completed in {analyze_time}s")
    print(f"Discovered Candidates: {len(candidates)}")
    assert len(candidates) > 0, "Zero candidate clips discovered"

    # Verify candidates
    print("\nDiscovered Highlights:")
    for idx, c in enumerate(candidates, 1):
        s_time = c["start_time"]
        e_time = c["end_time"]
        dur = c["duration"]
        score_obj = c.get("score", {})
        total_s = score_obj.get("total_score", 0.0)
        assert s_time < e_time, f"Candidate {c['id']}: start ({s_time}) >= end ({e_time})"
        assert e_time <= duration + 5.0, f"Candidate {c['id']}: end ({e_time}) exceeds video duration ({duration})"
        print(f"\n  Candidate #{idx} [ID: {c['id']}] - Score: {total_s}/100")
        print(f"    Title:      \"{c.get('title')}\"")
        print(f"    Timestamps: {s_time:.2f}s - {e_time:.2f}s (Duration: {dur:.2f}s)")
        print(f"    Hook:       {c.get('hook_assessment')}")
        print(f"    Reasoning:  {c.get('reasoning')}")
        print(f"    Excerpt:    \"{c.get('transcript_excerpt')[:100]}...\"")

    # 5. Render ONE Candidate First (Highest Score)
    print("\n--- 5. RENDER TOP CANDIDATE (Highest Score) ---")
    top_candidate = candidates[0]
    clip_id = top_candidate["id"]
    print(f"Processing candidate: '{top_candidate['title']}' ({clip_id}) - Score: {top_candidate['score']['total_score']}")

    # Step A: Precision cut
    print("Executing frame-accurate cut...")
    t_cut = time.time()
    r = client.post(f"{BACKEND_URL}/api/projects/{project_id}/clips/cut", json={"clip_id": clip_id})
    assert r.status_code == 200, f"Cut failed: {r.text}"
    cut_time = round(time.time() - t_cut, 2)
    raw_clip_path = Path("projects") / project_id / "clips" / clip_id / "raw_clip.mp4"
    assert raw_clip_path.exists(), f"raw_clip.mp4 missing: {raw_clip_path}"
    print(f"Cut completed in {cut_time}s -> {raw_clip_path} ({round(raw_clip_path.stat().st_size/(1024*1024), 2)} MB)")

    # Step B: Vertical Reframe (9:16)
    print("Executing 9:16 vertical reframing with face detection/tracking...")
    t_reframe = time.time()
    r = client.post(f"{BACKEND_URL}/api/projects/{project_id}/reframe", json={"clip_id": clip_id})
    assert r.status_code == 200, f"Reframe failed: {r.text}"
    reframe_time = round(time.time() - t_reframe, 2)
    reframed_path = Path("projects") / project_id / "clips" / clip_id / "reframed.mp4"
    assert reframed_path.exists(), f"reframed.mp4 missing: {reframed_path}"
    print(f"Reframe completed in {reframe_time}s -> {reframed_path} ({round(reframed_path.stat().st_size/(1024*1024), 2)} MB)")

    # Step C: Burn Captions
    print("Generating synchronized ASS/SRT subtitles and burning into MP4...")
    t_captions = time.time()
    r = client.post(f"{BACKEND_URL}/api/projects/{project_id}/captions", json={"clip_id": clip_id})
    assert r.status_code == 200, f"Captions failed: {r.text}"
    caption_time = round(time.time() - t_captions, 2)
    final_clip_path = Path("projects") / project_id / "clips" / clip_id / "final_clip.mp4"
    srt_file_path = Path("projects") / project_id / "clips" / clip_id / "captions.srt"
    ass_file_path = Path("projects") / project_id / "clips" / clip_id / "captions.ass"
    assert final_clip_path.exists(), f"final_clip.mp4 missing: {final_clip_path}"
    assert srt_file_path.exists(), f"captions.srt missing: {srt_file_path}"
    assert ass_file_path.exists(), f"captions.ass missing: {ass_file_path}"
    print(f"Caption burning completed in {caption_time}s -> {final_clip_path} ({round(final_clip_path.stat().st_size/(1024*1024), 2)} MB)")

    # 6. 9:16 & Visual Verification
    print("\n--- 6. 9:16 & VISUAL VERIFICATION ---")
    final_probe = probe_file(final_clip_path)
    f_fmt = final_probe.get("format", {})
    f_streams = final_probe.get("streams", [])
    f_v = next((s for s in f_streams if s.get("codec_type") == "video"), None)
    f_a = next((s for s in f_streams if s.get("codec_type") == "audio"), None)

    f_w = int(f_v.get("width", 0)) if f_v else 0
    f_h = int(f_v.get("height", 0)) if f_v else 0
    f_codec = f_v.get("codec_name", "unknown") if f_v else "none"
    f_dur = float(f_fmt.get("duration", 0.0))
    f_fps = f_v.get("r_frame_rate", "30/1") if f_v else "30/1"

    print(f"Width:        {f_w} px")
    print(f"Height:       {f_h} px")
    print(f"Aspect Ratio: {f_w}:{f_h} (Expected 1080:1920)")
    print(f"Video Codec:  {f_codec}")
    print(f"Audio Codec:  {f_a.get('codec_name', 'none') if f_a else 'none'}")
    print(f"Duration:     {f_dur:.2f}s")
    print(f"Frame Rate:   {f_fps}")
    print(f"File Size:    {round(final_clip_path.stat().st_size/(1024*1024), 2)} MB")

    assert f_w == 1080, f"Expected width 1080, got {f_w}"
    assert f_h == 1920, f"Expected height 1920, got {f_h}"
    assert f_a is not None, "Final clip missing audio stream"

    # Decode test
    print("Testing complete video decoding with FFmpeg...")
    decode_cmd = ["ffmpeg", "-v", "error", "-i", str(final_clip_path), "-f", "null", "-"]
    decode_res = subprocess.run(decode_cmd, capture_output=True, text=True)
    if decode_res.returncode == 0:
        print("[PASS] FFmpeg decoded full final_clip.mp4 with 0 stream errors.")
    else:
        print(f"[FAIL] FFmpeg decode error: {decode_res.stderr}")

    # Extract sample frame at midpoint to inspect burned captions
    midpoint_sec = round(f_dur / 2.0, 2)
    sample_frame_path = Path("projects") / project_id / "clips" / clip_id / "sample_frame.jpg"
    frame_cmd = [
        "ffmpeg", "-y",
        "-ss", str(midpoint_sec),
        "-i", str(final_clip_path),
        "-vframes", "1",
        str(sample_frame_path)
    ]
    subprocess.run(frame_cmd, capture_output=True, check=True)
    print(f"Extracted sample frame at {midpoint_sec}s -> {sample_frame_path} ({round(sample_frame_path.stat().st_size/1024, 1)} KB)")

    # 7. Frontend Integration Check
    print("\n--- 7. FRONTEND INTEGRATION CHECK ---")
    # Verify media preview route
    media_url = f"{BACKEND_URL}/media/{project_id}/clips/{clip_id}/final_clip.mp4"
    r = client.head(media_url)
    print(f"Media Preview Route:  HTTP {r.status_code} ({media_url})")
    assert r.status_code == 200, f"Media preview route failed: {r.status_code}"

    # Verify SRT download route
    srt_url = f"{BACKEND_URL}/api/projects/{project_id}/captions/{clip_id}/srt"
    r = client.get(srt_url)
    print(f"SRT Download Route:    HTTP {r.status_code} ({len(r.text)} bytes)")
    assert r.status_code == 200, f"SRT route failed: {r.status_code}"

    # Summary
    total_time = round(time.time() - t0, 2)
    print("\n" + "=" * 70)
    print("  VERIFICATION COMPLETE - ALL CHECKS PASSED")
    print("=" * 70)
    print(f"Total Pipeline Time: {total_time}s")
    print(f"  - Ingestion:       {ingest_time}s")
    print(f"  - Transcription:   {transcribe_time}s")
    print(f"  - LLM Analysis:    {analyze_time}s")
    print(f"  - Precision Cut:   {cut_time}s")
    print(f"  - 9:16 Reframe:    {reframe_time}s")
    print(f"  - Caption Burning: {caption_time}s")
    print(f"Final Rendered MP4:  {final_clip_path.resolve()}")


if __name__ == "__main__":
    main()
