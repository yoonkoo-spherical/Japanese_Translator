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
# 1. 환경 설정 및 클라이언트 초기화
# ==========================================
st.set_page_config(page_title="Pro AI 통역기", layout="centered")

# 세션 상태 초기화
if "last_request_time" not in st.session_state:
    st.session_state.last_request_time = 0
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

# API 키 및 클라이언트 설정
try:
    if "GEMINI_API_KEY" in st.secrets:
        # 최신 google-genai 클라이언트 생성
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ Secrets에서 GEMINI_API_KEY를 확인하세요.")
        st.stop()
except Exception as e:
    st.error(f"⚠️ 초기화 오류: {e}")
    st.stop()

# ==========================================
# 2. 핵심 유틸리티 함수
# ==========================================

def ask_gemini_v2(contents, model_id="gemini-flash-lite-latest"):
    """
    최신 SDK 기반의 안전한 API 호출 함수
    """
    # 중복 요청 방지 (2초 쿨다운)
    curr_time = time.time()
    if curr_time - st.session_state.last_request_time < 2:
        return None
    
    if st.session_state.is_processing:
        return None

    st.session_state.is_processing = True
    st.session_state.last_request_time = curr_time

    try:
        # 최신 호출 방식 적용
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1024
            )
        )
        return response
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ 사용량 초과. 잠시 후 시도하세요.")
        else:
            st.error(f"⚠️ 서버 응답 오류: {e}")
        return None
    finally:
        st.session_state.is_processing = False

def convert_audio_to_wav(audio_bytes):
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except:
        return io.BytesIO(audio_bytes)

def parse_response(text):
    parts = text.split('|')
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    return text, "", ""

# ==========================================
# 3. 가독성 중심 UI 컴포넌트 (검은색 글자 카드)
# ==========================================

def display_card(title, main, sub=None, footer=None):
    html = f"""
    <div style="padding: 20px; border-radius: 12px; background-color: #ffffff; 
                border: 1px solid #e0e0e0; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <p style="color: #666; font-size: 14px; margin-bottom: 5px;">{title}</p>
        <p style="color: #000000; font-size: 26px; font-weight: bold; margin-bottom: 8px; line-height: 1.4;">{main}</p>
        {f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 8px;"><p style="color: #444; font-size: 16px; margin: 0;"><b>{sub}</b></p></div>' if sub else ''}
        {f'<p style="color: #888; font-size: 13px; margin-top: 10px; text-align: right;">{footer}</p>' if footer else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 4. 메인 화면 구성
# ==========================================

st.title("🇯🇵 Pro AI 통역기")
st.caption("SDK 3.0 업그레이드 완료 | 지연 시간 최적화")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📸 사진", "🎤 대화"])

# 텍스트 번역
with tab1:
    text_in = st.text_area("한국어 입력", height=100, key="txt_in")
    if st.button("번역하기", use_container_width=True):
        if text_in:
            with st.spinner(".."):
                prompt = f"Translate Korean to Japanese. Format: Japanese|Romaji|Meaning. Input: {text_in}"
                res = ask_gemini_v2(prompt)
                if res:
                    jp, rom, mean = parse_response(res.text)
                    display_card("🇯🇵 일본어 결과", jp, rom, f"뜻: {mean}")

# 사진 번역
with tab2:
    file = st.file_uploader("사진 선택", type=['jpg', 'png', 'webp'])
    if file:
        img = Image.open(file)
        st.image(img, use_column_width=True)
        if st.button("사진 해석하기", use_container_width=True):
            with st.spinner(".."):
                prompt = "Find Japanese text and translate to Korean. Format: 1. [Summary] 2. [Original] -> [Translation]"
                res = ask_gemini_v2([prompt, img])
                if res:
                    st.markdown("---")
                    st.markdown(res.text)

# 음성 대화
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.info("🇰🇷 한국어")
        aud_kr = mic_recorder(start_prompt="🎤 말하기", stop_prompt="⏹️ 멈춤", key='mic_kr')
    with c2:
        st.warning("🇯🇵 일본어")
        aud_jp = mic_recorder(start_prompt="🎤 말하기", stop_prompt="⏹️ 멈춤", key='mic_jp')

    if aud_kr:
        with st.spinner(".."):
            wav = convert_audio_to_wav(aud_kr['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as src:
                    data = r.record(src)
                    stt = r.recognize_google(data, language='ko-KR')
                    st.caption(f"인식: {stt}")
                    res = ask_gemini_v2(f"Translate to Japanese. Format: Japanese|Romaji|Meaning. Input: {stt}")
                    if res:
                        jp, rom, mean = parse_response(res.text)
                        display_card("🇯🇵 번역 결과", jp, rom, f"뜻: {mean}")
            except:
                st.error("인식 실패")

    if aud_jp:
        with st.spinner(".."):
            wav = convert_audio_to_wav(aud_jp['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as src:
                    data = r.record(src)
                    stt = r.recognize_google(data, language='ja-JP')
                    st.caption(f"인식: {stt}")
                    res = ask_gemini_v2(f"Translate Japanese to Korean: {stt}")
                    if res:
                        display_card("🇰🇷 한국어 결과", res.text)
            except:
                st.error("인식 실패")

