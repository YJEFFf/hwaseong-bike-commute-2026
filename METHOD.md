# 보고서와 분석 코드의 대응

| 보고서 내용 | 코드 | 집계 결과 |
|---|---|---|
| 자전거망의 연결 덩어리·끊긴 지점 | `commute/scripts/03_gaps_and_shared.py` | `gaps_summary.csv` |
| 보행자 겸용 구간 | `commute/scripts/03_gaps_and_shared.py` | `shared_path_share.csv` |
| 공장 일자리 접근성 | `commute/scripts/02_commute_access.py` | `commute_access.csv`, `commute_access_by_dong.csv` |
| 공장과 자전거 시설의 거리 | `commute/scripts/05_factory_distance.py` | `factory_distance_to_bike.csv` |
| 연결 우선순위·탄소 시나리오 | `commute/scripts/04_gap_priority_commute.py` | `gap_bundle_carbon.csv` |
| 최대 사업장 제외 등 민감도 | `commute/scripts/07_sensitivity.py` | `sensitivity_round2.csv` |
| 기존·재선정 연결 묶음 비교 | 저장된 대상 고정 비교 집계 | `bundle_target_sensitivity.csv` |
| 보고서 그림 생성 | `commute/scripts/06_figures.py` | 실행 환경에서 생성 |

집계 파일은 모두 `commute/results/`에 있습니다. 입력 주소를 좌표로 바꾸는 코드는 `01_geocode_factories.py`, 재시도 코드는 `01b_geocode_retry.py`입니다.

기준 속도는 15km/h, 15분 이동 거리는 3.75km입니다. 기본 망 접속 반경은 150m이며 300m 접속 민감도도 비교했습니다. 끊긴 지점은 현장 확인값이 아닌 지도상 선 끝점 간 간격을 사용합니다. 상위 연결 묶음은 앞서 선택한 연결의 효과를 반영하는 탐욕 선택으로 계산합니다.

보고서의 AI 활용, 해석, 한계는 [AI_USAGE.md](AI_USAGE.md)와 [README.md](README.md)에 정리했습니다.
