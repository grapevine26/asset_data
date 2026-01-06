import json
import time
from supabase import create_client

# ==========================================
# 1. 설정 (Supabase 정보 입력)
# ==========================================
# ⚠️ 주의: 여기에는 'anon' 키 말고 'service_role' 키를 넣는 게 좋습니다.
# (RLS 정책 무시하고 관리자 권한으로 쓰기 위함)
SUPABASE_URL = "https://zyujgtojeireqjeyfbnb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5dWpndG9qZWlyZXFqZXlmYm5iIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NjUyNDUwMiwiZXhwIjoyMDgyMTAwNTAyfQ.Z6xSRGdL_JHSFO47IyZhKpx-jHQirw8cfvq9XN8gIJ8"  # 쓰기 권한이 있는 Service Role Key 권장

BATCH_SIZE = 100  # 한 번에 업로드할 개수 (100~500 추천)
FILENAME = 'game_data_final.json'

# ==========================================
# 2. 클라이언트 생성
# ==========================================
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_data():
    print(f"📂 '{FILENAME}' 파일 로딩 중...")

    try:
        with open(FILENAME, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ 파일을 찾을 수 없습니다. collector.py를 먼저 실행해주세요.")
        return

    total_count = len(data)
    print(f"🚀 총 {total_count}개의 게임 데이터를 업로드합니다.\n")

    # ==========================================
    # 3. 배치 업로드 (Chunking)
    # ==========================================
    success_count = 0

    for i in range(0, total_count, BATCH_SIZE):
        batch = data[i: i + BATCH_SIZE]
        current_batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total_count // BATCH_SIZE) + 1

        try:
            # upsert: 있으면 덮어쓰고, 없으면 새로 만듦 (중복 방지)
            response = supabase.table('trading_games').upsert(batch).execute()

            count = len(batch)
            success_count += count
            print(f"   ✅ [{current_batch_num}/{total_batches}] {count}개 저장 완료 ({success_count}/{total_count})")

            # API 보호를 위해 아주 살짝 쉼
            time.sleep(0.1)

        except Exception as e:
            print(f"   ❌ [{current_batch_num}/{total_batches}] 에러 발생: {e}")
            # 에러 나도 멈추지 않고 다음 배치 시도

    print(f"\n🎉 최종 완료! 총 {success_count}개의 게임이 DB에 저장되었습니다.")


if __name__ == "__main__":
    upload_data()