import sys
import types
sys.modules['pyaudioop'] = types.ModuleType('pyaudioop')

import streamlit as st
# ... ကျန်တဲ့ code တွေ ဆက်ရှိပါစေ ...

import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
from pydub import AudioSegment
import tempfile
from moviepy import VideoFileClip

# Page configuration
st.set_page_config(page_title="Movie Recap AI (Burmese)", layout="wide")

# Title and Description
st.title("🎬 Movie Recap AI (Burmese)")
st.markdown("""
ဒီ App လေးက YouTube Transcript သို့မဟုတ် Video ဖိုင်တွေကနေ စိတ်လှုပ်ရှားစရာကောင်းတဲ့ **မြန်မာဘာသာစကား Movie Recap Script** တွေ ဖန်တီးပေးပြီး အသံဖိုင်ပါ တစ်ခါတည်း ထုတ်ပေးမှာ ဖြစ်ပါတယ်။
""")

# Sidebar for API Key
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Google Gemini API Key", type="password")
    st.info("Gemini API Key ကို [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ အခမဲ့ ရယူနိုင်ပါတယ်။")

# Function to generate script using Gemini
def generate_recap_script(input_text, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        You are a professional Movie Recap YouTuber. Your task is to rewrite the following movie transcript into an engaging, exciting, and storytelling "Movie Recap Style" script in Burmese (Myanmar) language.
        
        Guidelines:
        - Use an exciting and engaging tone.
        - Use natural, spoken Burmese (not too formal).
        - Focus on the key plot points and emotional moments.
        - Add a hook at the beginning and a conclusion at the end.
        - Ensure the flow is smooth for a voice-over.
        
        Transcript:
        {input_text}
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# Function to generate audio using edge-tts
async def generate_audio(text, output_mp3, output_wav):
    voice = "my-MM-NilarNeural" # Female Burmese voice in edge-tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_mp3)
    audio = AudioSegment.from_mp3(output_mp3)
    audio.export(output_wav, format="wav")

# Main UI
tab1, tab2 = st.tabs(["YouTube Transcript", "Video Upload"])
input_content = ""

with tab1:
    transcript_input = st.text_area("Paste YouTube Transcript here:", height=300)
    if transcript_input:
        input_content = transcript_input

with tab2:
    uploaded_file = st.file_uploader("Upload Video (Max 500MB)", type=["mp4", "mkv", "avi"])
    if uploaded_file:
        if uploaded_file.size > 500 * 1024 * 1024:
            st.error("File size exceeds 500MB limit.")
        else:
            with st.spinner("Extracting audio from video..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
                    tmp_video.write(uploaded_file.read())
                    video_path = tmp_video.name
                try:
                    video = VideoFileClip(video_path)
                    st.warning("Video upload detected. Note: Direct video-to-script requires Speech-to-Text processing. For now, please provide the transcript in Tab 1.")
                    input_content = f"Video file: {uploaded_file.name}"
                except Exception as e:
                    st.error(f"Error processing video: {e}")

# Process Button
if st.button("Generate Movie Recap"):
    if not api_key:
        st.error("Please enter your Gemini API Key in the sidebar.")
    elif not input_content:
        st.error("Please provide a transcript or upload a video.")
    else:
        with st.spinner("Generating Burmese Script..."):
            burmese_script = generate_recap_script(input_content, api_key)
            if burmese_script.startswith("Error:"):
                st.error(burmese_script)
            else:
                st.subheader("Generated Burmese Script")
                st.write(burmese_script)
                st.session_state['burmese_script'] = burmese_script

# Audio Generation Section
if 'burmese_script' in st.session_state:
    st.divider()
    st.subheader("Audio Generation")
    if st.button("Generate Audio"):
        with st.spinner("Converting script to audio..."):
            mp3_path = "recap_audio.mp3"
            wav_path = "recap_audio.wav"
            try:
                asyncio.run(generate_audio(st.session_state['burmese_script'], mp3_path, wav_path))
                st.success("Audio generated successfully!")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("MP3 Player")
                    st.audio(mp3_path, format="audio/mp3")
                    with open(mp3_path, "rb") as f:
                        st.download_button("Download MP3", f, "recap.mp3", "audio/mp3")
                with col2:
                    st.write("WAV Player")
                    st.audio(wav_path, format="audio/wav")
                    with open(wav_path, "rb") as f:
                        st.download_button("Download WAV", f, "recap.wav", "audio/wav")
            except Exception as e:
                st.error(f"Audio generation failed: {e}")

# Footer
st.markdown("---")
st.caption("Created with ❤️ for Movie Recap Creators")
