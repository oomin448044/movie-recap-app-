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
import cv2
import numpy as np
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips, TextClip, CompositeVideoClip

# Page configuration
st.set_page_config(page_title="Web (1): AI Burmese Movie Narrator Pro", layout="wide")

st.title("🎬 Web (1): AI Burmese Movie Narrator Pro")
st.markdown("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# Sidebar for Settings
with st.sidebar:
    st.header("Settings")
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

# Blur function for original subtitles
def blur_bottom(image):
    h, w, _ = image.shape
    # Define bottom 20% area for blurring original subtitles
    bottom_h = int(h * 0.2)
    bottom_part = image[h-bottom_h:h, 0:w]
    # Apply Gaussian Blur
    blurred_bottom = cv2.GaussianBlur(bottom_part, (51, 51), 0)
    image[h-bottom_h:h, 0:w] = blurred_bottom
    return image

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
                
                # 2026 Stable Models
                model_names = ["gemini-2.5-flash", "gemini-3.0-flash", "gemini-2.5-pro"]
                model = None
                model_name_used = ""

                for m_name in model_names:
                    try:
                        model = genai.GenerativeModel(m_name, safety_settings=safety_settings)
                        model_name_used = m_name
                        break 
                    except Exception:
                        continue
                
                if not model:
                    st.error("❌ Gemini Model ကို ရှာမတွေ့ပါ။ API Key မှန်မမှန် သို့မဟုတ် Model Access ရှိမရှိ ပြန်စစ်ပေးပါ။")
                    st.stop()
                else:
                    st.info(f"✅ Using Gemini Model: {model_name_used}")
                
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
                    
                    # Parsing content
                    titles_part = ""
                    hashtags_part = ""
                    recap_part = ""
                    
                    if "[TITLES]" in full_text:
                        parts = full_text.split("[TITLES]")
                        if len(parts) > 1:
                            subparts = parts[1].split("[HASHTAGS]")
                            titles_part = subparts[0].strip()
                            if len(subparts) > 1:
                                recap_split = subparts[1].split("[RECAP]")
                                hashtags_part = recap_split[0].strip()
                                if len(recap_split) > 1:
                                    recap_part = recap_split[1].strip()
                    
                    if not recap_part: recap_part = full_text
                    
                    st.success("✨ Social Media Ready Content!")
                    
                    # Feature 1: Titles with Copy Buttons
                    st.subheader("📌 Catchy Titles (Click to Copy)")
                    if titles_part:
                        titles = [t.strip() for t in titles_part.split('\n') if t.strip()]
                        for i, t in enumerate(titles[:3]):
                            col_t, col_b = st.columns([0.8, 0.2])
                            col_t.code(t)
                            # Using Streamlit copy to clipboard if available or info message
                            if col_b.button(f"Copy Title {i+1}", key=f"copy_{i}"):
                                st.write(f'<script>navigator.clipboard.writeText("{t}");</script>', unsafe_allow_html=True)
                                st.toast(f"Title {i+1} Copied!")
                    
                    st.subheader("📝 Full Recap Script:")
                    st.write(recap_part)
                    
                    # Generate Burmese Audio
                    with st.spinner("Generating Burmese narration audio..."):
                        audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                        asyncio.run(generate_speech(recap_part, audio_path))
                    
                    # Feature 2: Process Video with Blur and Burmese Subtitles
                    with st.spinner("Processing video (Blurring & Subtitling)..."):
                        video_clip = VideoFileClip(video_path)
                        audio_clip = AudioFileClip(audio_path)
                        
                        # Apply blur to original subtitles
                        video_blurred = video_clip.fl_image(blur_bottom)
                        video_muted = video_blurred.without_audio()
                        
                        # Handle duration
                        if audio_clip.duration > video_muted.duration:
                            last_frame = video_muted.get_frame(video_muted.duration - 0.1)
                            freeze_frame = ImageClip(last_frame).set_duration(audio_clip.duration - video_muted.duration)
                            video_final = concatenate_videoclips([video_muted, freeze_frame])
                        else:
                            video_final = video_muted.subclip(0, audio_clip.duration)
                        
                        # Add Burmese Subtitles Overlay
                        # Font path check
                        font_path = "pyidaungsu-1.2.ttf"
                        if not os.path.exists(font_path):
                            st.warning("Font file 'pyidaungsu-1.2.ttf' not found. Subtitles might not appear correctly.")
                            font_path = None
                        
                        # Split recap into sentences for subtitling
                        sentences = re.split(r'(?<=[။])\s*', recap_part)
                        subtitles = []
                        duration_per_sentence = video_final.duration / max(len(sentences), 1)
                        
                        for i, sentence in enumerate(sentences):
                            if sentence.strip():
                                txt_clip = TextClip(
                                    sentence.strip(),
                                    fontsize=24,
                                    color='white',
                                    font=font_path,
                                    stroke_color='black',
                                    stroke_width=1,
                                    method='caption',
                                    size=(video_final.w * 0.8, None)
                                ).set_start(i * duration_per_sentence).set_duration(duration_per_sentence).set_position(('center', video_final.h - 60))
                                subtitles.append(txt_clip)
                        
                        # Combine everything
                        final_video_with_subs = CompositeVideoClip([video_final] + subtitles)
                        final_video_with_subs = final_video_with_subs.set_audio(audio_clip)
                        
                        output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                        final_video_with_subs.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=24)
                    
                    st.success("✅ Video Processing Complete!")
                    st.video(output_video_path)
                    with open(output_video_path, "rb") as f:
                        st.download_button("⬇️ Download Final Video (MP4)", f, "my_movie_recap.mp4", "video/mp4")
                    
                    # Clean up
                    video_clip.close()
                    audio_clip.close()
                    if os.path.exists(audio_path): os.remove(audio_path)
                    if os.path.exists(output_video_path): os.remove(output_video_path)
                
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
