import streamlit as st
import pandas as pd
from io import BytesIO

# 1. 페이지 설정
st.set_page_config(page_title="멘소래담 재고 검색 엔진 v2", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    .stDownloadButton > button { width: 100%; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 가용 재고 실시간 조회 시스템 (영업팀/채널 확장 버전)")

# --- 엑셀 변환 헬퍼 함수 ---
def to_excel(df, cols):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df[cols].to_excel(writer, index=False, sheet_name='재고조회결과')
    return output.getvalue()

# 2. 데이터 로드 및 정밀 전처리
@st.cache_data
def load_filtered_data():
    # 최신 업로드 파일명으로 반영
    stock_file = "Sales_Stock_260519.xlsx"
    mapping_file = "매핑용.xlsx"
    
    try:
        # --- 1) 데이터 로드 ---
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        # 매핑용 Sheet2 로드
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()

        # --- 2) 매핑 키 정규화 ---
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        # --- 3) 데이터 병합 (Sales Team, Channel 추가) ---
        # 요구하신 시트 내 Sales Team과 Channel 열을 선택 영역에 추가합니다.
        target_cols = ['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']
        mapping_sub = df_channel[target_cols].dropna(subset=['제품코드_key'])
        mapping_sub = mapping_sub.drop_duplicates('제품코드_key')
        
        df_merged = pd.merge(
            df_stock, 
            mapping_sub, 
            left_on="상품코드_key", 
            right_on="제품코드_key", 
            how="left"
        )
        
        df_merged.drop(columns=['상품코드_key', '제품코드_key'], inplace=True)
        
        # 컬럼명 한글 직관화 정리
        df_merged.rename(columns={
            'Customer': '납품처',
            '상품코드': '제품코드', 
            '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수',
            '합계수량': '환산(재고 수)',
            'Remarks': '특이사항',
            'Sales Team': '영업팀',
            'Channel': '채널'
        }, inplace=True)

        # --- 4) 로트번호 및 가용 재고 필터링 ---
        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[df_merged['로트번호'] != '']
        df_merged = df_merged[df_merged['로트번호'].str.lower() != 'nan']
        df_merged = df_merged[~df_merged['로트번호'].str.contains('폐기', na=False)]
        
        # --- 5) 상품바코드 클렌징 ---
        if '상품바코드' in df_merged.columns:
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'\.0$', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'[?？]', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.strip()

        # --- 6) 유효일자 형식 지정 ---
        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        # 영업팀, 채널 결측치 처리 및 문자열 정리
        df_merged['영업팀'] = df_merged['영업팀'].fillna('미분류').astype(str).str.strip()
        df_merged['채널'] = df_merged['채널'].fillna('미분류').astype(str).str.strip()
            
        return df_merged
    except Exception as e:
        st.error(f"❌ 데이터 결합 및 정제 과정 중 오류가 발생했습니다: {e}")
        st.stop()

df_raw = load_filtered_data()

# --- 검색 설정: 단독 납품(전용) 필터 토글 ---
st.markdown("---")
col_setting, col_blank = st.columns([1, 2])
with col_setting:
    st.markdown("### ⚙️ 검색 설정")
    is_exclusive = st.toggle("🌟 단독 납품(전용) 제품만 보기")

if is_exclusive:
    df = df_raw[~df_raw['납품처'].astype(str).str.contains(',', na=False)]
else:
    df = df_raw.copy()
st.markdown("---")

# 화면 출력 및 데이터 시각화 스타일 구성
display_cols = ['납품처', '영업팀', '채널', '제품코드', '상품명', '로트번호', '유효일자', '잔여일수', '환산(재고 수)', '특이사항', '상품바코드']

dashboard_config = {
    "잔여일수": st.column_config.ProgressColumn("잔여일수 (위험도)", format="%d 일", min_value=0, max_value=1095),
    "환산(재고 수)": st.column_config.NumberColumn("가용 재고", format="%d 개"),
    "유효일자": st.column_config.DateColumn("유효일자 📅"),
    "특이사항": st.column_config.TextColumn("특이사항 📝")
}

# 3. 사용자 검색 탭 세분화 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "🏢 납품처(Customer) 기준", 
    "👥 영업팀(Sales Team) 기준", 
    "📺 채널(Channel) 기준", 
    "🔍 제품명/코드 기준"
])

# --- 탭 1: 납품처별 검색 ---
with tab1:
    col_input1, col_down1 = st.columns([3, 1])
    with col_input1:
        all_customers = df['납품처'].dropna().unique().tolist()
        customer_set = set()
        for c in all_customers:
            for part in str(c).split(','):
                customer_set.add(part.strip())
        unique_customers = sorted(list(customer_set))
        target_customer = st.selectbox("조회할 납품처를 선택하세요", ["선택하세요"] + unique_customers, key="sb_customer")
    
    if target_customer != "선택하세요":
        result1 = df[df['납품처'].str.contains(target_customer, na=False, regex=False)]
        with col_down1:
            st.write(""); st.write("")
            st.download_button(label="📥 엑셀 다운로드", data=to_excel(result1, display_cols), file_name=f"{target_customer}_재고현황.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="btn_dl1")
        st.metric("가용 재고 건수", f"{len(result1)} 건")
        st.dataframe(result1[display_cols], use_container_width=True, hide_index=True, height=500, column_config=dashboard_config)

# --- 탭 2: 영업팀별 검색 ---
with tab2:
    col_input2, col_down2 = st.columns([3, 1])
    with col_input2:
        # 콤마로 다중 지정된 팀이 있을 경우를 위해 결합 분리 처리
        all_teams = df['영업팀'].unique().tolist()
        team_set = set()
        for t in all_teams:
            for part in str(t).split(','):
                team_set.add(part.strip())
        unique_teams = sorted(list(team_set))
        target_team = st.selectbox("조회할 영업팀(Sales Team)을 선택하세요", ["선택하세요"] + unique_teams, key="sb_team")
        
    if target_team != "선택하세요":
        result2 = df[df['영업팀'].str.contains(target_team, na=False, regex=False)]
        with col_down2:
            st.write(""); st.write("")
            st.download_button(label="📥 엑셀 다운로드", data=to_excel(result2, display_cols), file_name=f"{target_team}_영업팀_재고현황.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="btn_dl2")
        st.metric("영업팀 배정 재고 건수", f"{len(result2)} 건")
        st.dataframe(result2[display_cols], use_container_width=True, hide_index=True, height=500, column_config=dashboard_config)

# --- 탭 3: 채널별 검색 ---
with tab3:
    col_input3, col_down3 = st.columns([3, 1])
    with col_input3:
        all_channels = df['채널'].unique().tolist()
        channel_set = set()
        for ch in all_channels:
            for part in str(ch).split(','):
                channel_set.add(part.strip())
        unique_channels = sorted(list(channel_set))
        target_channel = st.selectbox("조회할 채널(Channel)을 선택하세요", ["선택하세요"] + unique_channels, key="sb_channel")
        
    if target_channel != "선택하세요":
        result3 = df[df['채널'].str.contains(target_channel, na=False, regex=False)]
        with col_down3:
            st.write(""); st.write("")
            st.download_button(label="📥 엑셀 다운로드", data=to_excel(result3, display_cols), file_name=f"{target_channel}_채널_재고현황.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="btn_dl3")
        st.metric("채널 가용 재고 건수", f"{len(result3)} 건")
        st.dataframe(result3[display_cols], use_container_width=True, hide_index=True, height=500, column_config=dashboard_config)

# --- 탭 4: 제품별 상세 검색 ---
with tab4:
    search_input = st.text_input("제품명 또는 코드를 입력하세요 (예: 아크네스, 립밤, 수입코드...)")
    if search_input:
        result4 = df[
            df['상품명'].str.contains(search_input, case=False, na=False, regex=False) |
            df['제품코드'].str.contains(search_input, case=False, na=False, regex=False)
        ]
        if not result4.empty:
            st.download_button(label="📥 결과 전체 다운로드", data=to_excel(result4, display_cols), file_name="검색결과_재고.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="btn_dl4")
            st.metric("검색 결과", f"{len(result4)} 건")
            st.dataframe(result4[display_cols], use_container_width=True, hide_index=True, height=500, column_config=dashboard_config)
        else:
            st.warning("가용한 제품 정보가 없습니다. 검색어나 검색 설정을 다시 확인해주세요.")
