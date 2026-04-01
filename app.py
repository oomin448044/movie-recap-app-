import sys
import types
# Fix for pydub error in Streamlit Cloud
sys.modules['pyaudioop'] = types.ModuleType('pyaudioop')

import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import tempfile
from moviepy import VideoFileClip

# Page configuration
st.set_page_config(page_title="Burmese Movie Recap AI", layout="wide")

st.title("🎬 Burmese Movie Recap AI (Male Narrator)")
st.markdown("YouTube Transcript သို့မဟုတ် Video ကနေ စိတ်လှုပ်ရှားစရာကောင်းတဲ့ **မြန်မာယောကျာ်းသံ ဇာတ်ကြောင်းပြော Script** ဖန်တီးပေးပါတယ်။")

# Sidebar for API Key
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.info("API Key မရှိသေးရင် [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Input Section
tab1, tab2 = st.tabs(["YouTube Transcript", "Video Upload"])

transcript_text = ""

with tab1:
    transcript_input = st.text_area("Paste YouTube Transcript here:", height=200)
    if transcript_input:
        transcript_text = transcript_input

with tab2:
    video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])
    if video_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            tmp_video.write(video_file.read())
            video_path = tmp_video.name
        
        with st.spinner("Extracting context from video..."):
            try:
                # For context, we use the filename. 
                # For full video analysis, Gemini 1.5 Pro would be needed.
                transcript_text = f"This is a movie recap for the video file: {video_file.name}"
                st.success("Video uploaded successfully!")
            except Exception as e:
                st.error(f"Error: {e}")

# AI Processing
if st.button("Generate Movie Recap Script"):
    if not api_key:
        st.warning("Please enter your API Key in the sidebar.")
    elif not transcript_text:
        st.warning("Please provide a transcript or upload a video.")
    else:
        with st.spinner("AI က မြန်မာလို Recap Script ရေးပေးနေပါတယ်..."):
            # Improved prompt for better genre matching and storytelling
            prompt = f"""
            You are a professional Movie Recap Narrator. 
            Rewrite the following transcript into an engaging, exciting, and storytelling Movie Recap Script in BURMESE language.
            
            STRICT RULES:
            1. Use an exciting and storytelling tone (like popular movie recap channels).
            2. Stay 100% faithful to the original genre. If it's a romance, make it romantic. If it's action, make it thrilling.
            3. Do NOT hallucinate or change the story to a different genre.
            4. Use natural, spoken Burmese (not formal book language).
            5. Start with an engaging hook and end with a summary.
            6. Format the script for a male narrator.
            
            Transcript: {transcript_text}
            """
            try:
                response = model.generate_content(prompt)
                st.session_state['recap_script'] = response.text
                st.subheader("Generated Burmese Script:")
                st.write(response.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

# Audio Generation
if 'recap_script' in st.session_state:
    if st.button("Generate Audio (Male Narrator Voiceover)"):
        with st.spinner("မြန်မာယောကျာ်းသံ (Thiha) နဲ့ ဇာတ်ကြောင်းပြောနေပါတယ်..."):
            try:
                # Use Thiha (Male) voice for a more natural narration feel
                voice = "my-MM-ThihaNeural"
                communicate = edge_tts.Communicate(st.session_state['recap_script'], voice)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
                    asyncio.run(communicate.save(tmp_mp3.name))
                    mp3_path = tmp_mp3.name
                
                st.success("Audio generated successfully!")
                st.audio(mp3_path, format="audio/mp3")
                
                with open(mp3_path, "rb") as f:
                    st.download_button("Download Voiceover (MP3)", f, "movie_recap_male.mp3", "audio/mp3")
            except Exception as e:
                st.error(f"Audio Error: {e}")
