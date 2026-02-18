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
    """API 클라이언트를 메모리에 상주시켜 연결 속도를 향상시킴"""
    if "GEMINI_API_KEY" in st.secrets:
        return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ Secrets에서 GEMINI_API_KEY를 설정하십시오.")
        st.stop()

client = get_client()

# 제공된 목록 중 가장 빠르고 경량화된 모델 선택
# gemini-2.0-flash-lite 혹은 gemini-2.0-flash-lite-001 권장
SELECTED_MODEL = "gemini-2.0-flash-lite"

# ==========================================
# 2. UI 및 유틸리티
# ==========================================

def display_card(title, main, sub=None):
    """가독성을 극대화한 검은색 텍스트 카드 UI"""
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
    """모든 스트리밍 응답을 통합 처리하는 핵심 함수"""
    full_text = ""
    try:
        # 스트리밍 요청 개시
        stream = client.models.generate_content_stream(
            model=SELECTED_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        for chunk in stream:
            if chunk.text:
                full_text += chunk.text
                # 실시간 마크다운 출력으로 체감 속도 향상
                placeholder.write(f"⌛ **생성 중:** {full_text}")
        
        # 완료 후 최종 가독성 카드 출력
        placeholder.empty()
        if "|" in full_text:
            parts = full_text.split('|')
            display_card(f"{title_prefix} 결과", parts[0].strip(), parts[1].strip() if len(parts)>1 else None)
            if len(parts) > 2:
                st.caption(f"의미: {parts[2].strip()}")
        else:
            display_card(f"{title_prefix} 결과", full_text)
            
    except Exception as e:
        placeholder.error(f"❌ API 통신 오류: {e}")

# ==========================================
# 3. 기능별 Fragment (부분 실행 단위)
# ==========================================

@st.fragment
def fragment_text():
    """텍스트 번역 영역: 입력 시 전체 페이지 Rerun 방지"""
    text_input = st.text_area("한국어 입력", placeholder="번역할 문장을 입력하십시오.", key="txt_area")
    if st.button("즉시 번역", use_container_width=True):
        if text_input:
            out = st.empty()
            prompt = f"Translate Korean to Japanese naturally. Format: Japanese|Romaji|Meaning. Input: {text_input}"
            stream_translator(prompt, out)

@st.fragment
def fragment_image():
    """사진 분석 영역"""
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
    """음성 통역 영역"""
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
st.caption(f"사용 중인 모델: {SELECTED_MODEL} | Streaming On")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📸 사진", "🎤 대화"])

with tab1: fragment_text()
with tab2: fragment_image()
with tab3: fragment_voice()
