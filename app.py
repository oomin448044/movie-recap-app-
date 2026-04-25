import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import time
import re
import subprocess

# --- Configuration ---
st.set_page_config(page_title="Burmese AI Movie Narrator Pro", layout="wide")

st.title("🎬 Burmese AI Movie Narrator Pro")
st.info("Video ကိုကြည့်ပြီး မြန်မာလိုရှင်းပြပေးသော AI စနစ်")

# --- Sidebar ---
with st.sidebar:
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.markdown("[Get API Key](https://aistudio.google.com/app/apikey)")

# --- TTS ---
async def generate_burmese_audio(text, output_path):
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-5%", pitch="-2Hz")
    await communicate.save(output_path)

def get_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(result.stdout.strip())
    except:
        return 0.0

# --- Upload ---
video_file = st.file_uploader("Upload Video", type=["mp4", "mov", "avi"])

if video_file and api_key:
    video_path = "input.mp4"
    with open(video_path, "wb") as f:
        f.write(video_file.read())

    st.video(video_path)

    if st.button("Start"):
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("models/gemini-1.5-flash")

        gen_file = genai.upload_file(video_path, mime_type="video/mp4")

        prompt = "Describe this video in Burmese narration."

        response = model.generate_content([gen_file, prompt])
        text = response.text

        audio_path = "audio.mp3"
        asyncio.run(generate_burmese_audio(text, audio_path))

        temp_video = "temp.mp4"
        subprocess.run([
            "ffmpeg", "-i", video_path, "-r", "24",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            temp_video, "-y"
        ])

        v_dur = get_duration(temp_video)
        a_dur = get_duration(audio_path)

        output = "final.mp4"

        if a_dur > v_dur:
            cmd = [
                "ffmpeg", "-i", temp_video, "-i", audio_path,
                "-filter_complex",
                f"[0:v]fps=24,tpad=stop_mode=clone:stop_duration={a_dur-v_dur},setsar=1:1[v];"
                f"[1:a]atrim=start=0,asetpts=PTS-STARTPTS[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac",
                output, "-y"
            ]
        else:
            cmd = [
                "ffmpeg", "-i", temp_video, "-i", audio_path,
                "-filter_complex",
                "[0:v]fps=24,setsar=1:1[v];[1:a]atrim=start=0,asetpts=PTS-STARTPTS[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac",
                "-t", str(a_dur),
                output, "-y"
            ]

        subprocess.run(cmd)

        st.success("Done")
        st.video(output)
