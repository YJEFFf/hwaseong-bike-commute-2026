# 길은 있는데 왜 차로 출근할까

**화성시 끊긴 자전거도로와 공장 출퇴근** · 팀 북적북적(장준용, 허예준)

한겨레 × 숲과나눔 「AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전」 분석 코드 제출용 저장소입니다.

화성시 자전거망의 끊긴 지점과 공장 앞 진입 구간이 일자리 접근에 미치는 영향을 분석합니다. 공식 GIS와 OpenStreetMap을 결합한 망에서 출퇴근 도달, 연결 우선순위, 조건부 탄소 감축량을 계산합니다.

## 심사자를 위한 안내

| 확인할 내용 | 위치 |
|---|---|
| 보고서의 핵심 분석 코드 | [commute/scripts/](commute/scripts/) |
| 보고서와 대응하는 집계 결과 | [commute/results/](commute/results/) |
| 분석 순서·보고서와 코드의 대응 | [METHOD.md](METHOD.md) |
| 설치·테스트·입력자료 준비 | [REPRODUCE.md](REPRODUCE.md) |
| 데이터 출처·공개 범위 | [DATA_SOURCES.md](DATA_SOURCES.md) |
| AI 활용 내역 | [AI_USAGE.md](AI_USAGE.md) |
| 원본 코드와 파일 해시 | [SOURCE_SNAPSHOT.json](SOURCE_SNAPSHOT.json) |

## 주요 결과

- 자전거망은 **383개 연결 덩어리**로 나뉘며, 1km 미만 덩어리는 **322개**입니다.
- 자전거 15분 직선거리 안의 공장 일자리 중 자전거망으로 닿는 몫은 **3.7%**입니다.
- 최대 종업원 집계점을 제외하면 기본 **5.5%**, 공장 진입 개선 시 **8.1%**, 틈 연결과 진입 개선을 함께 적용하면 **11.1%**입니다.

거리 기반 접근 가능성을 분석한 결과입니다. 실제 자전거 출퇴근 수요나 전환 효과를 관측한 값이 아니며, 지도상 끊김의 현장 통행 가능성은 확인하지 못했습니다. 탄소 결과는 전환율과 배출계수 가정에 따른 시나리오입니다.

## 빠른 시작

```bash
git clone https://github.com/YJEFFf/hwaseong-bike-commute-2026.git
cd hwaseong-bike-commute-2026
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-verified.txt
python -X utf8 -m pytest -q commute/tests
```

집계 CSV는 바로 열람할 수 있습니다. 전체 분석 재실행에는 별도 원자료와 지오코딩 입력이 필요하며, 공개 저장소를 복제하는 것만으로 원자료가 준비되지는 않습니다. 자세한 조건은 [재현 안내](REPRODUCE.md)를 참고하세요.

## 폴더 구성

```text
commute/scripts/   보고서의 출퇴근·단절·우선순위·민감도 분석
commute/results/   좌표와 연락처를 포함하지 않는 집계 CSV
commute/data/      통근 수단 통계와 출처
commute/tests/     출퇴근 분석 검증
analysis/         네트워크·접근성 등 공통 분석 모듈
scripts/          입력자료 수집·기초 망 구축·공통 실행 도구
tests/            공통 모듈 검증
params/           탄소 계산 매개변수
```

분석 코드와 집계는 원본 커밋 `47b93cf`에서 선별했으며 수치·알고리즘을 변경하지 않았습니다. 문서는 공개 제출용으로 새로 정리했습니다.
