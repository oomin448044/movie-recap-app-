import sys
import types
# Fix for pydub error in Streamlit Cloud
sys.modules["pyaudioop"] = types.ModuleType("pyaudioop")

import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import tempfile
import time
import re
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips

# Page configuration
st.set_page_config(page_title="Web (1): AI Burmese Movie Narrator Pro", layout="wide")

st.title("🎬 Web (1): AI Burmese Movie Narrator Pro")
st.markdown("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# Sidebar for Settings
with st.sidebar:
    st.header("Settings")
    # API Key Input - Secure way
    api_key = st.text_input("Enter Gemini API Key:", type="password", help="API Key ကို GitHub ပေါ် မတင်မိပါစေနဲ့။ Google က ချက်ချင်း ပိတ်လိုက်ပါလိမ့်မယ်။")
    st.info("API Key မရှိသေးရင် VPN ဖွင့်ပြီး [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

# Input Section - Video Upload
st.subheader("📁 Upload Video")
video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])

video_path = None
if video_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
        tmp_video.write(video_file.read())
        video_path = tmp_video.name
    st.video(video_path)

async def generate_speech(text, output_path):
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural")
    await communicate.save(output_path)

if video_path and api_key:
    if st.button("Generate Movie Recap"):
        with st.spinner("AI က Video ကိုကြည့်ပြီး ဇာတ်ကြောင်းပြောရန် ပြင်ဆင်နေပါတယ်..."):
            try:
                genai.configure(api_key=api_key)
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                
                # Using the most stable model names to avoid 404 errors
                # Removed '-latest' suffix to avoid API version compatibility issues
                model_names = ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-pro"]
                model = None
                model_name_used = ""

                for m_name in model_names:
                    try:
                        model = genai.GenerativeModel(m_name, safety_settings=safety_settings)
                        # Test if model exists by calling a simple prompt
                        # Some versions might fail here if the name is not found
                        model_name_used = m_name
                        break 
                    except Exception:
                        continue
                
                if not model:
                    st.error("❌ Gemini Model ကို ရှာမတွေ့ပါ။ API Key မှန်မမှန် သို့မဟုတ် Model Access ရှိမရှိ ပြန်စစ်ပေးပါ။")
                    st.stop()
                else:
                    st.info(f"✅ Using Gemini Model: {model_name_used}")
                
                # Upload video to Gemini
                video_file_ai = genai.upload_file(path=video_path)
                with st.spinner("Uploading video to AI server..."):
                    while video_file_ai.state.name == "PROCESSING":
                        time.sleep(5)
                        video_file_ai = genai.get_file(video_file_ai.name)

                if video_file_ai.state.name == "FAILED":
                    st.error("Video processing failed. Please try another video.")
                    st.stop()

                prompt = """
                Analyze this video and provide a detailed movie recap in BURMESE language.
                STORYTELLING STYLE:
                - Act as a professional human movie narrator.
                - Use natural, engaging, and emotional Burmese storytelling style.
                - Avoid robotic or formal language.
                OUTPUT FORMAT:
                [TITLES]
                Title 1
                Title 2
                Title 3
                [HASHTAGS]
                #tag1 #tag2 #tag3
                [RECAP]
                The detailed story...
                """
                
                response = model.generate_content([video_file_ai, prompt])
                
                if not response.candidates:
                    st.error("AI က ဒီ Video ကို ပိတ်ပင်ထားပါတယ် (Blocked)။")
                else:
                    full_text = response.text
                    
                    # Improved regex to handle titles and hashtags safely
                    # Using more robust matching logic
                    titles_part = ""
                    hashtags_part = ""
                    recap_part = ""
                    
                    if "[TITLES]" in full_text:
                        titles_part = full_text.split("[TITLES]")[1].split("[HASHTAGS]")[0].strip()
                    if "[HASHTAGS]" in full_text:
                        hashtags_part = full_text.split("[HASHTAGS]")[1].split("[RECAP]")[0].strip()
                    if "[RECAP]" in full_text:
                        recap_part = full_text.split("[RECAP]")[1].strip()
                    else:
                        recap_part = full_text # Fallback
                    
                    st.success("✨ Social Media Ready Content!")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("📌 Catchy Titles")
                        if titles_part:
                            titles = titles_part.split('\n')
                            for t in titles[:3]: 
                                if t.strip(): st.code(t.strip())
                    with col2:
                        st.subheader("🔥 Trending Hashtags")
                        if hashtags_part: 
                            st.code(hashtags_part.strip())
                    
                    st.subheader("📝 Full Recap Script:")
                    st.write(recap_part)
                    
                    # Generate Burmese Audio
                    with st.spinner("Generating Burmese narration audio..."):
                        audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                        asyncio.run(generate_speech(recap_part, audio_path))
                    
                    # Process Video with MoviePy
                    with st.spinner("Combining video and audio... (This may take a few minutes)"):
                        video_clip = VideoFileClip(video_path)
                        audio_clip = AudioFileClip(audio_path)
                        
                        # Mute original video
                        video_muted = video_clip.without_audio()
                        
                        # Handle duration mismatch
                        if audio_clip.duration > video_muted.duration:
                            # Freeze last frame if audio is longer
                            last_frame = video_muted.get_frame(video_muted.duration - 0.1)
                            freeze_frame = ImageClip(last_frame).set_duration(audio_clip.duration - video_muted.duration)
                            video_final = concatenate_videoclips([video_muted, freeze_frame])
                        else:
                            # Trim video if audio is shorter
                            video_final = video_muted.subclip(0, audio_clip.duration)
                        
                        # Set audio
                        final_video = video_final.set_audio(audio_clip)
                        output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                        final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=24)
                    
                    st.success("✅ Video Processing Complete!")
                    st.video(output_video_path)
                    with open(output_video_path, "rb") as f:
                        st.download_button("⬇️ Download Final Video (MP4)", f, "my_movie_recap.mp4", "video/mp4")
                    
                    # Clean up
                    video_clip.close()
                    audio_clip.close()
                    if os.path.exists(audio_path): os.remove(audio_path)
                    if os.path.exists(output_video_path): os.remove(output_video_path)
                
                # Delete uploaded file from Gemini
                genai.delete_file(video_file_ai.name)
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
            finally:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)

elif not api_key and video_path:
    st.warning("⚠️ Please enter your API Key in the sidebar.")
