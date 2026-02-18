import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
from streamlit_mic_recorder import mic_recorder

# 1. 페이지 설정
st.set_page_config(page_title="초고속 일본어 번역기", layout="centered")

# 2. API 키 보안 로드
try:
    if "GEMINI_API_KEY" in st.secrets:
        GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=GENAI_API_KEY)
    else:
        st.error("API 키 설정을 확인하세요.")
        st.stop()
except Exception:
    st.error("Secrets 파일을 찾을 수 없습니다.")
    st.stop()

# 3. 모델 설정 (속도 최적화: Flash-8b 모델 사용)
# 8b 모델은 기존 Flash보다 가볍고 응답 속도가 훨씬 빠릅니다.
@st.cache_resource
def get_model():
    return genai.GenerativeModel('gemini-flash-lite-latest')

model = get_model()

# 이미지 리사이징 함수 (속도 향상 핵심)
def resize_image(image, max_width=800):
    width_percent = (max_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(width_percent)))
    return image.resize((max_width, h_size), Image.Resampling.LANCZOS)

st.title("⚡ 초고속 AI 통역기")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 사진", "🎤 음성"])

# --- [기능 1] 텍스트 번역 ---
with tab1:
    text_input = st.text_area("입력 (자동감지)", height=100)
    if st.button("⚡ 번역", key="btn_text"):
        if text_input:
            with st.spinner(".."):
                try:
                    # 프롬프트를 간결하게 하여 생성 토큰을 줄임
                    prompt = f"""
                    Translate efficiently.
                    Korean -> Japanese
                    Japanese -> Korean
                    Text: {text_input}
                    """
                    response = model.generate_content(prompt)
                    st.success(response.text)
                except Exception as e:
                    st.error(f"Error: {e}")

# --- [기능 2] 사진 번역 (이미지 압축 적용) ---
with tab2:
    uploaded_file = st.file_uploader("사진 선택", type=['jpg', 'png', 'webp'])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        
        # 이미지 리사이징 (전송 속도 및 분석 속도 향상)
        resized_image = resize_image(image)
        st.image(resized_image, caption="압축된 이미지", use_column_width=True)
        
        if st.button("⚡ 해석"):
            with st.spinner("분석 중.."):
                try:
                    # 요약 요청을 제거하고 번역만 요청하여 속도 확보
                    image_prompt = """
                    Locate Japanese text and translate to Korean.
                    Format: [Original] -> [Translation]
                    """
                    response = model.generate_content([image_prompt, resized_image])
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Error: {e}")

# --- [기능 3] 음성 통역 ---
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.info("🇰🇷 나")
        audio_kr = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️", key='kr')
    with col2:
        st.warning("🇯🇵 상대")
        audio_jp = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️", key='jp')

    if audio_kr:
        with st.spinner(".."):
            try:
                audio_bytes = io.BytesIO(audio_kr['bytes'])
                r = sr.Recognizer()
                with sr.AudioFile(audio_bytes) as source:
                    audio_data = r.record(source)
                    stt_text = r.recognize_google(audio_data, language='ko-KR')
                    st.write(f"🗣️ {stt_text}")
                    
                    # 짧고 명확한 지시
                    res = model.generate_content(f"Translate Korean to Japanese: {stt_text}")
                    st.success(f"🇯🇵 {res.text}")
            except:
                st.error("인식 실패")

    if audio_jp:
        with st.spinner(".."):
            try:
                audio_bytes = io.BytesIO(audio_jp['bytes'])
                r = sr.Recognizer()
                with sr.AudioFile(audio_bytes) as source:
                    audio_data = r.record(source)
                    stt_text = r.recognize_google(audio_data, language='ja-JP')
                    st.write(f"🗣️ {stt_text}")
                    
                    res = model.generate_content(f"Translate Japanese to Korean: {stt_text}")
                    st.success(f"🇰🇷 {res.text}")
            except:
                st.error("인식 실패")

