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
from moviepy import VideoFileClip, AudioFileClip

# Page configuration
st.set_page_config(page_title="Burmese Movie Recap Video AI", layout="wide")

st.title("🎬 Burmese Movie Recap Video AI")
st.markdown("Video တင်လိုက်ရုံနဲ့ **မြန်မာနောက်ခံစကားပြောပါတဲ့ Video အသစ်** ကို အလိုအလျောက် ဖန်တီးပေးပါတယ်။")

# Sidebar for API Key
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.info("API Key မရှိသေးရင် VPN ဖွင့်ပြီး [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

# Input Section
video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])

if video_file and api_key:
    # Save uploaded video to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
        tmp_video.write(video_file.read())
        video_path = tmp_video.name
    
    st.subheader("Original Video Preview:")
    st.video(video_path)
    
    if st.button("Generate Burmese Recap Video"):
        with st.spinner("AI က မြန်မာလို Recap Script ရေးပြီး Video နဲ့ အသံကို ပေါင်းစပ်နေပါတယ်..."):
            try:
                # 1. Configure AI
                genai.configure(api_key=api_key)
                
                # Try to find an available model automatically
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name)
                
                # 2. Generate Script
                prompt = f"Create a short, exciting movie recap script in BURMESE for a video titled: {video_file.name}. Use natural spoken Burmese for a male narrator. Make it engaging and storytelling style."
                response = model.generate_content(prompt)
                recap_script = response.text
                
                st.subheader("Generated Script:")
                st.write(recap_script)
                
                # 3. Generate Audio (Voiceover)
                voice = "my-MM-ThihaNeural"
                communicate = edge_tts.Communicate(recap_script, voice)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                    asyncio.run(communicate.save(tmp_audio.name))
                    audio_path = tmp_audio.name
                
                # 4. Combine Video and New Audio
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_path)
                
                # Set the new audio to the video clip
                final_video = video_clip.with_audio(audio_clip)
                
                # Save the final merged video
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
                
                # 5. Display and Download
                st.success("မြန်မာနောက်ခံစကားပြောပါတဲ့ Video အသစ် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!")
                st.video(output_video_path)
                
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Final Video (MP4)", f, "my_movie_recap_final.mp4", "video/mp4")
                
                # Cleanup
                video_clip.close()
                audio_clip.close()
                
            except Exception as e:
                st.error(f"Error: {e}. Please check if your API Key is correct and has access to Gemini models.")
elif not api_key and video_file:
    st.warning("Please enter your API Key in the sidebar.")
