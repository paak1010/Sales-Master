import streamlit as st
import pandas as pd
from io import BytesIO

# 1. 페이지 설정
st.set_page_config(page_title="멘소래담 재고 마스터링 시스템", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    .stDownloadButton > button { width: 100%; background-color: #007bff; color: white; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 가용 재고 마스터링 및 조회 시스템")

# --- 엑셀 변환 헬퍼 함수 ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='재고조회결과')
    return output.getvalue()

# 2. 데이터 로드 및 정밀 전처리
@st.cache_data
def load_filtered_data():
    stock_file = "Sales_Stock_260519.xlsx"
    mapping_file = "매핑용.xlsx"
    
    try:
        # --- 1) 데이터 로드 ---
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()

        # --- 2) 매핑 키 정규화 ---
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        # --- 3) 데이터 병합 (요청하신 열만 정확히 추출) ---
        target_cols = ['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']
        mapping_sub = df_channel[target_cols].dropna(subset=['제품코드_key']).drop_duplicates('제품코드_key')
        
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드_key", right_on="제품코드_key", how="left")
        df_merged.drop(columns=['상품코드_key', '제품코드_key'], inplace=True)
        
        df_merged.rename(columns={
            'Customer': '납품처', '상품코드': '제품코드', '화주LOT': '로트번호',
            '입수량(BOX)': '박스입수', '합계수량': '수량',
            'Remarks': '특이사항', 'Sales Team': '영업팀', 'Channel': '채널'
        }, inplace=True)

        # --- 4) 로트번호 및 가용 재고 필터링 ---
        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[df_merged['로트번호'] != '']
        df_merged = df_merged[df_merged['로트번호'].str.lower() != 'nan']
        df_merged = df_merged[~df_merged['로트번호'].str.contains('폐기', na=False)]
        
        # --- 5) 🚨 피드백 반영: 납품처 및 특이사항에서 "-" 제외 로직 ---
        df_merged['납품처'] = df_merged['납품처'].fillna('미지정').astype(str).str.strip()
        df_merged = df_merged[df_merged['납품처'] != '-']
        
        df_merged['영업팀'] = df_merged['영업팀'].fillna('미분류').astype(str).str.strip()
        df_merged['채널'] = df_merged['채널'].fillna('미분류').astype(str).str.strip()
        df_merged['특이사항'] = df_merged['특이사항'].fillna('').astype(str).str.strip()

        # --- 6) 상품바코드 및 유효일자 클렌징 ---
        if '상품바코드' in df_merged.columns:
            df_merged['상품바코드'] = df_merged['상품바코드'].fillna('').astype(str)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'\.0$', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.replace(r'[?？]', '', regex=True)
            df_merged['상품바코드'] = df_merged['상품바코드'].str.strip()

        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"❌ 데이터 전처리 중 오류 발생: {e}")
        st.stop()

# 정제된 가용 원본 데이터 로드
df_raw = load_filtered_data()

# ==========================================
# 3. 다차원 사이드바/상단 필터 구성
# ==========================================
st.markdown("### 🔍 검색 및 필터링")
col_f1, col_f2, col_f3 = st.columns([1, 1, 2])

with col_f1:
    all_customers = df_raw['납품처'].unique().tolist()
    customer_set = set(part.strip() for c in all_customers for part in str(c).split(',') if part.strip() != '-')
    unique_customers = sorted(list(customer_set))
    selected_customer = st.selectbox("🏢 납품처 선택", ["전체"] + unique_customers)

with col_f2:
    all_teams = df_raw['영업팀'].unique().tolist()
    team_set = set(part.strip() for t in all_teams for part in str(t).split(',') if part.strip() != '-')
    unique_teams = sorted(list(team_set))
    selected_team = st.selectbox("👥 영업팀 선택", ["전체"] + unique_teams)

with col_f3:
    search_q = st.text_input("📝 제품명 또는 제품코드 검색", placeholder="검색어를 입력하세요 (예: 아크네스, 고쿠쥰, ME...)")

# 데이터 필터링 적용
df_filtered = df_raw.copy()
if selected_customer != "전체":
    df_filtered = df_filtered[df_filtered['납품처'].str.contains(selected_customer, na=False, regex=False)]
if selected_team != "전체":
    df_filtered = df_filtered[df_filtered['영업팀'].str.contains(selected_team, na=False, regex=False)]
if search_q:
    df_filtered = df_filtered[
        df_filtered['상품명'].str.contains(search_q, case=False, na=False, regex=False) |
        df_filtered['제품코드'].str.contains(search_q, case=False, na=False, regex=False)
    ]

# ==========================================
# 4. 🚨 핵심 기능: 바코드/ME코드 기준 그룹화 및 토글 UI
# ==========================================
st.markdown("---")

if not df_filtered.empty:
    # 1) 메인 가시성을 위해 바코드와 제품코드 기준으로 묶어서 합계수량(총 가용 재고) 산출
    # 그룹화할 때 텍스트 정보(상품명, 납품처, 영업팀, 채널, 특이사항) 리스트의 첫 항목을 유지
    group_cols = ['상품바코드', '제품코드']
    
    df_main = df_filtered.groupby(group_cols).agg({
        '상품명': 'first',
        '납품처': 'first',
        '영업팀': 'first',
        '채널': 'first',
        '특이사항': 'first',
        '수량': 'sum' # 재고 수량 합산
    }).reset_index()
    
    df_main.rename(columns={'수량': '총 가용 재고'}, inplace=True)
    
    # 다운로드용 데이터 준비
    st.download_button(
        label="📥 필터링된 전체 내역 엑셀 다운로드",
        data=to_excel(df_filtered),
        file_name="가용재고_조회결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown(f"### 📊 요약 재고 현황판 (총 {len(df_main)}개의 핵심 품목)")
    
    # 메인 서머리 테이블 출력 (물리적 상태, 전용 여부 제외됨)
    main_display_cols = ['납품처', '영업팀', '채널', '제품코드', '상품명', '총 가용 재고', '특이사항', '상품바코드']
    st.dataframe(
        df_main[main_display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "총 가용 재고": st.column_config.NumberColumn("총 가용 재고", format="%d 개"),
            "특이사항": st.column_config.TextColumn("비고/특이사항 📝")
        }
    )
    
    # 2) 상세 정보 조회를 위한 토글 섹션 (끝에 버튼을 누르는 효과 대체)
    st.markdown("### 🔍 품목별 상세 LOT 및 유효일자 내역")
    st.caption("아래 품목을 클릭하면 해당 제품 내에 포함된 상세 로트(LOT) 번호, 유효일자, 잔여일수 명세를 바로 확인할 수 있습니다.")
    
    for idx, row in df_main.iterrows():
        bcode = row['상품바코드']
        pcode = row['제품코드']
        pname = row['상품명']
        total_stock = row['총 가용 재고']
        
        # 해당 그룹에 속하는 상세 로트 데이터들만 원본에서 필터링하여 추출
        df_detail = df_filtered[
            (df_filtered['상품바코드'] == bcode) & 
            (df_filtered['제품코드'] == pcode)
        ][['로트번호', '유효일자', '잔여일수', '수량']].copy()
        
        df_detail.rename(columns={'수량': '로트별 수량'}, inplace=True)
        
        # 익스팬더 타이틀을 버튼처럼 활용
        with st.expander(f"📋 [조회] {pcode} | {pname} (총 {total_stock}개)"):
            st.dataframe(
                df_detail,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "잔여일수": st.column_config.ProgressColumn("잔여일수", format="%d 일", min_value=0, max_value=1095),
                    "로트별 수량": st.column_config.NumberColumn("로트별 수량", format="%d 개"),
                    "유효일자": st.column_config.DateColumn("유효일자 📅")
                }
            )
else:
    st.warning("⚠️ 필터 조건에 부합하는 가용 재고 데이터가 존재하지 않습니다.")
