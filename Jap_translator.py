import streamlit as st
from deep_translator import GoogleTranslator
import easyocr
import speech_recognition as sr
from PIL import Image
import numpy as np
import io
from streamlit_mic_recorder import mic_recorder

# 페이지 설정
st.set_page_config(page_title="일본어 번역기", layout="mobile")

# OCR 리더 로드 (캐싱 적용, CPU 모드)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ja', 'en'], gpu=False)

# 번역 함수
def do_translate(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception as e:
        return "번역 실패"

st.title("🇯🇵 일본 여행용 번역기")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 카메라", "🎤 동시통역"])

# --- 1. 텍스트 번역 ---
with tab1:
    st.caption("한국어 ↔ 일본어 자동 감지")
    txt_input = st.text_area("입력", height=100)
    if st.button("번역하기"):
        if txt_input:
            # 한글 포함 여부로 번역 방향 결정
            if any('가' <= c <= '힣' for c in txt_input):
                res = do_translate(txt_input, 'ja')
                st.success(f"🇯🇵 일본어: {res}")
            else:
                res = do_translate(txt_input, 'ko')
                st.success(f"🇰🇷 한국어: {res}")

# --- 2. 사진 번역 (카메라 촬영) ---
with tab2:
    st.caption("일본어 텍스트가 있는 곳을 촬영하세요.")
    img_file = st.camera_input("촬영")

    if img_file:
        with st.spinner("텍스트 분석 중..."):
            bytes_data = img_file.getvalue()
            image = Image.open(io.BytesIO(bytes_data))
            
            # OCR 실행
            reader = load_ocr()
            result = reader.readtext(np.array(image), detail=0)
            text_result = " ".join(result)
            
            if text_result:
                st.info(f"원문: {text_result}")
                trans_result = do_translate(text_result, 'ko')
                st.success(f"번역: {trans_result}")
            else:
                st.warning("텍스트를 인식하지 못했습니다.")

# --- 3. 음성 번역 (양방향) ---
with tab3:
    st.write("### 🇰🇷 내가 말하기 (한국어)")
    # 한국어 음성 입력 -> 일본어 출력
    audio_kr = mic_recorder(
        start_prompt="🔴 한국어 녹음 시작", 
        stop_prompt="⏹️ 종료", 
        key='rec_kr'
    )

    if audio_kr:
        with st.spinner("한국어 인식 중..."):
            audio_data = io.BytesIO(audio_kr['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(audio_data) as source:
                    audio_content = r.record(source)
                    # 한국어 인식 (ko-KR)
                    text = r.recognize_google(audio_content, language='ko-KR')
                    st.info(f"나(한국어): {text}")
                    
                    # 일본어로 번역
                    trans = do_translate(text, 'ja')
                    st.success(f"🇯🇵 번역: {trans}")
            except:
                st.error("인식 실패. 다시 말씀해주세요.")

    st.divider() # 구분선

    st.write("### 🇯🇵 상대방 말 듣기 (일본어)")
    # 일본어 음성 입력 -> 한국어 출력
    audio_jp = mic_recorder(
        start_prompt="🔴 일본어 녹음 시작", 
        stop_prompt="⏹️ 종료", 
        key='rec_jp'
    )

    if audio_jp:
        with st.spinner("일본어 인식 중..."):
            audio_data = io.BytesIO(audio_jp['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(audio_data) as source:
                    audio_content = r.record(source)
                    # 일본어 인식 (ja-JP)
                    text = r.recognize_google(audio_content, language='ja-JP')
                    st.info(f"상대(일본어): {text}")
                    
                    # 한국어로 번역
                    trans = do_translate(text, 'ko')
                    st.success(f"🇰🇷 번역: {trans}")
            except:
                st.error("인식 실패. 다시 시도해주세요.")