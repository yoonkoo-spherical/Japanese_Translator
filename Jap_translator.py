import streamlit as st
from google import genai
from google.genai import types
import speech_recognition as sr
from PIL import Image
import io
import time
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment

# ==========================================
# 1. 초기 설정 및 클라이언트 캐싱
# ==========================================
st.set_page_config(page_title="Ultra-Fast AI 통역기", layout="centered")

@st.cache_resource
def get_client():
    if "GEMINI_API_KEY" in st.secrets:
        return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ Secrets에서 GEMINI_API_KEY를 설정하십시오.")
        st.stop()

client = get_client()

# 사용자 목록에 있는 'gemini-flash-latest'(1.5 Flash)를 사용합니다.
# 만약 이 모델이 느리다면 "gemini-2.5-flash-lite"로 교체해 보십시오.
SELECTED_MODEL = "gemini-flash-latest"

# ==========================================
# 2. UI 및 유틸리티
# ==========================================

def display_card(title, main, sub=None):
    html = f"""
    <div style="padding: 15px; border-radius: 10px; background-color: #ffffff; 
                border: 1px solid #ddd; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <p style="color: #666; font-size: 13px; margin: 0;">{title}</p>
        <p style="color: #000; font-size: 26px; font-weight: bold; margin: 5px 0; line-height:1.2;">{main}</p>
        {f'<p style="color: #444; font-size: 16px; margin: 0;"><b>{sub}</b></p>' if sub else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def stream_translator(contents, placeholder, title_prefix="🇯🇵 일본어"):
    full_text = ""
    try:
        stream = client.models.generate_content_stream(
            model=SELECTED_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        for chunk in stream:
            if chunk.text:
                full_text += chunk.text
                placeholder.write(f"⌛ **번역 중:** {full_text}")
        
        placeholder.empty()
        if "|" in full_text:
            parts = full_text.split('|')
            display_card(f"{title_prefix} 결과", parts[0].strip(), parts[1].strip() if len(parts)>1 else None)
            if len(parts) > 2:
                st.caption(f"의미: {parts[2].strip()}")
        else:
            display_card(f"{title_prefix} 결과", full_text)
            
    except Exception as e:
        st.error(f"❌ API 에러 발생: {e}")

# ==========================================
# 3. 기능별 Fragment
# ==========================================

@st.fragment
def fragment_text():
    text_input = st.text_area("한국어 입력", placeholder="번역할 문장 입력", key="txt_area")
    if st.button("즉시 번역", use_container_width=True):
        if text_input:
            out = st.empty()
            prompt = f"Translate Korean to Japanese naturally. Format: Japanese|Romaji|Meaning. Input: {text_input}"
            stream_translator(prompt, out)

@st.fragment
def fragment_image():
    file = st.file_uploader("사진 업로드", type=['jpg', 'png', 'webp'], key="img_upl")
    if file:
        img = Image.open(file)
        st.image(img, use_container_width=True)
        if st.button("텍스트 추출 및 해석", use_container_width=True):
            out = st.empty()
            prompt = "이미지의 일본어 텍스트를 찾아 한국어로 번역하십시오. 형식: 1. [요약] 2. [원문] -> [번역]"
            stream_translator([prompt, img], out, title_prefix="📸 사진 해석")

@st.fragment
def fragment_voice():
    c1, c2 = st.columns(2)
    with c1:
        st.info("🇰🇷 한국어")
        aud_kr = mic_recorder(start_prompt="🎤 녹음", stop_prompt="⏹️ 완료", key='v_kr')
    with c2:
        st.warning("🇯🇵 일본어")
        aud_jp = mic_recorder(start_prompt="🎤 녹음", stop_prompt="⏹️ 완료", key='v_jp')

    r = sr.Recognizer()
    
    if aud_kr:
        with st.spinner("음성 분석 중..."):
            audio = AudioSegment.from_file(io.BytesIO(aud_kr['bytes']))
            buf = io.BytesIO()
            audio.export(buf, format="wav")
            buf.seek(0)
            with sr.AudioFile(buf) as src:
                data = r.record(src)
                try:
                    stt = r.recognize_google(data, language='ko-KR')
                    st.caption(f"인식 결과: {stt}")
                    out = st.empty()
                    stream_translator(f"Translate to Japanese: {stt}. Format: Japanese|Romaji|Meaning", out)
                except: st.error("인식 실패")

    if aud_jp:
        with st.spinner("음성 분석 중..."):
            audio = AudioSegment.from_file(io.BytesIO(aud_jp['bytes']))
            buf = io.BytesIO()
            audio.export(buf, format="wav")
            buf.seek(0)
            with sr.AudioFile(buf) as src:
                data = r.record(src)
                try:
                    stt = r.recognize_google(data, language='ja-JP')
                    st.caption(f"인식 결과: {stt}")
                    out = st.empty()
                    stream_translator(f"Translate Japanese to Korean: {stt}", out, title_prefix="🇰🇷 한국어")
                except: st.error("인식 실패")

# ==========================================
# 4. 메인 레이아웃
# ==========================================
st.title("🇯🇵 실시간 최적화 통역기")
st.caption(f"사용 모델: {SELECTED_MODEL} (1.5 Flash)")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📸 사진", "🎤 대화"])

with tab1: fragment_text()
with tab2: fragment_image()
with tab3: fragment_voice()
