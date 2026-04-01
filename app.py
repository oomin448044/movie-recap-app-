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
import time
from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip
from pytubefix import YouTube

# Page configuration
st.set_page_config(page_title="AI Burmese Movie Dubbing with Logo", layout="wide")

st.title("🎬 AI Burmese Movie Dubbing & Branding")
st.markdown("YouTube Link သို့မဟုတ် Video တင်လိုက်ရုံနဲ့ **မြန်မာလို တိုက်ရိုက်ဘာသာပြန်** ပေးပြီး သင့်ရဲ့ **Channel Logo** ကိုပါ တစ်ခါတည်း ထည့်သွင်းပေးပါတယ်။")

# Sidebar for Settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    logo_file = st.file_uploader("Upload Channel Logo (PNG/JPG):", type=["png", "jpg", "jpeg"])
    st.info("API Key မရှိသေးရင် VPN ဖွင့်ပြီး [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

# Input Section
tab1, tab2 = st.tabs(["YouTube Link", "Video Upload"])

video_path = None

with tab1:
    youtube_url = st.text_input("Paste YouTube Link here:")
    if youtube_url:
        with st.spinner("Downloading YouTube video..."):
            try:
                yt = YouTube(youtube_url)
                stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
                video_path = stream.download(output_path=tempfile.gettempdir())
                st.video(video_path)
            except Exception as e:
                st.error(f"YouTube Download Error: {e}")

with tab2:
    video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])
    if video_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            tmp_video.write(video_file.read())
            video_path = tmp_video.name
        st.video(video_path)

if video_path and api_key:
    if st.button("Generate Branded Dubbed Video"):
        with st.spinner("AI က ဘာသာပြန်ပြီး Logo ထည့်သွင်းနေပါတယ်..."):
            try:
                # 1. Configure AI and Find Model
                genai.configure(api_key=api_key)
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name)
                
                # 2. Upload Video to Gemini for Analysis
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file_ai = genai.get_file(video_file_ai.name)
                
                # 3. Generate Direct Translation Script (Strict Prompt)
                prompt = """
                Analyze this video and translate the original spoken dialogue into BURMESE language.
                STRICT RULES:
                1. ONLY translate what the characters are saying. 
                2. Do NOT add any commentary, narrator notes, or "Movie Recap" style introductions.
                3. Keep the translation concise so it matches the timing of the original speech.
                4. Use natural, spoken Burmese.
                5. Output ONLY the translated Burmese text.
                """
                response = model.generate_content([video_file_ai, prompt])
                dubbing_script = response.text
                
                st.subheader("Translated Burmese Script:")
                st.write(dubbing_script)
                
                # 4. Generate Audio (Voiceover)
                voice = "my-MM-ThihaNeural"
                communicate = edge_tts.Communicate(dubbing_script, voice)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                    asyncio.run(communicate.save(tmp_audio.name))
                    audio_path = tmp_audio.name
                
                # 5. Video Editing (Merging Audio & Adding Logo)
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_path)
                
                # Set new audio to the video
                video_with_audio = video_clip.with_audio(audio_clip)
                
                # Add Logo if uploaded
                if logo_file:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                        tmp_logo.write(logo_file.read())
                        logo_path = tmp_logo.name
                    
                    # Create Logo Clip (Position: Top-Left, Size: Height 50px)
                    logo = (ImageClip(logo_path)
                            .with_duration(video_clip.duration)
                            .resized(height=50) 
                            .with_position(("left", "top"))
                            .with_start(0))
                    
                    final_video = CompositeVideoClip([video_with_audio, logo])
                else:
                    final_video = video_with_audio
                
                # Save Final Video
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
                
                # 6. Display and Download
                st.success("Logo ပါဝင်တဲ့ မြန်မာဘာသာပြန် Video အသစ် ရပါပြီ!")
                st.video(output_video_path)
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Branded Video (MP4)", f, "my_branded_movie.mp4", "video/mp4")
                
                # Cleanup
                video_clip.close()
                audio_clip.close()
                genai.delete_file(video_file_ai.name)
                
            except Exception as e:
                st.error(f"Error: {e}")
elif not api_key and video_path:
    st.warning("Please enter your API Key in the sidebar.")
