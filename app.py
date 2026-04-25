import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import time
import re
import subprocess

# --- CONFIG ---
st.set_page_config(page_title="Burmese AI Movie Narrator Pro", layout="wide")

st.title("🎬 Burmese AI Movie Narrator Pro")

# --- SIDEBAR ---
with st.sidebar:
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.markdown("[Get API Key](https://aistudio.google.com/app/apikey)")

# --- SAFETY CHECK (FFmpeg) ---
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except:
        return False

# --- TTS ---
async def generate_burmese_audio(text, output_path):
    communicate = edge_tts.Communicate(
        text,
        "my-MM-ThihaNeural",
        rate="-5%",
        pitch="-2Hz"
    )
    await communicate.save(output_path)

# --- DURATION ---
def get_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0.0

# --- UI ---
video_file = st.file_uploader("📁 Upload Video", type=["mp4", "mov", "avi"])

if video_file and api_key:

    if not check_ffmpeg():
        st.error("❌ FFmpeg မရှိပါ (packages.txt မှာ ffmpeg ထည့်ပါ)")
        st.stop()

    genai.configure(api_key=api_key)

    video_path = "input.mp4"
    with open(video_path, "wb") as f:
        f.write(video_file.read())

    st.video(video_path)

    if st.button("🚀 Start Process"):

        try:
            model = genai.GenerativeModel("gemini-1.5-flash")

            st.info("Uploading video...")
            gen_file = genai.upload_file(video_path, mime_type="video/mp4")

            prompt = "Describe this video in Burmese narration."

            response = model.generate_content([gen_file, prompt])
            text = response.text

            audio_path = "audio.mp3"
            asyncio.run(generate_burmese_audio(text, audio_path))

            # --- convert video ---
            temp_video = "temp.mp4"
            subprocess.run([
                "ffmpeg", "-i", video_path, "-r", "24",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                temp_video, "-y"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            v_dur = get_duration(temp_video)
            a_dur = get_duration(audio_path)

            output = "final.mp4"

            if a_dur > v_dur:
                filter_cmd = (
                    f"[0:v]fps=24,tpad=stop_mode=clone:stop_duration={a_dur-v_dur},setsar=1:1[v];"
                    f"[1:a]atrim=start=0,asetpts=PTS-STARTPTS[a]"
                )
                t = None
            else:
                filter_cmd = "[0:v]fps=24,setsar=1:1[v];[1:a]atrim=start=0,asetpts=PTS-STARTPTS[a]"
                t = str(a_dur)

            cmd = ["ffmpeg", "-i", temp_video, "-i", audio_path,
                   "-filter_complex", filter_cmd,
                   "-map", "[v]", "-map", "[a]",
                   "-c:v", "libx264", "-c:a", "aac",
                   output, "-y"]

            if t:
                cmd.insert(-1, "-t")
                cmd.insert(-1, t)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                st.error(result.stderr)
                st.stop()

            st.success("✅ Done")

            st.video(output)

        except Exception as e:
            st.error(f"Error: {str(e)}")
