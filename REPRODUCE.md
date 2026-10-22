# 실행과 재현

## 환경과 테스트

Python 3.12 기준입니다. 저장소 루트에서 `python -m pip install -r requirements-verified.txt`로 의존성을 설치합니다. Windows에서도 `python -X utf8`을 사용합니다.

```bash
python -X utf8 -m pytest -q commute/tests
python -X utf8 -m pytest -q tests commute/tests
```

**2026-10-22 공개 제출본 검증:** Python 3.12 환경에서 전체 테스트 **281개 통과, 7개 생략**. 검증 환경은 `requirements-verified.txt`에 고정했습니다. 원본 코드의 의존성 명세 `requirements.txt`도 보존했습니다.

출퇴근 테스트는 합성 입력으로 거리·연결·집계 처리를 검증합니다. 전체 테스트 중 원본 비공개 산출물에 의존하는 검사는 공개본에서 생략되거나 실행에 추가 자료가 필요할 수 있습니다. 테스트 통과가 실제 교통 수요나 현장 통행 가능성을 검증하는 것은 아닙니다.

## 입력 준비

`data_manifest.json`에 원자료 파일 경로, 출처, 쿼리, 원본 해시가 있습니다. 수집 코드 `scripts/00_fetch.py`, `scripts/00b_fetch_public.py`와 함께 확인합니다. 원자료를 새로 수집하면 수집 시점 차이로 과거 결과와 달라질 수 있습니다.

출퇴근 분석은 `outputs/runs/loo_work/`에 준비된 망·인구·행정경계를 읽습니다. `scripts/run_all.py`는 기초 분석을 별도 `outputs/runs/<실행ID>/`에서 수행합니다. 당시 `loo_work` 스냅샷은 공개본에 포함하지 않았으므로 전체 재실행에는 이에 대응하는 입력 준비가 선행되어야 합니다. 임의로 빈 파일을 만들거나 저장된 집계 CSV를 원자료로 대체해서는 안 됩니다.

공장 입력은 `FACTORY_DIR`에 다음 파일을 준비합니다.

- `화성_공장등록_202402.xlsx`: 공장등록 원본
- `geocode_cache.csv`: 당시 좌표 변환 결과
- `manual_geocode.csv`: 당시 수동 보정 기록

원본에는 연락처가 있으므로 이 저장소에 올리지 않습니다. 좌표를 새로 생성할 경우 브이월드 인증키를 `VWORLD_KEY` 환경변수로 전달합니다. 기존 캐시와 수동 보정표 없이 당시 결과를 정확히 재현했다고 간주하지 않습니다.

## 출퇴근 분석 순서

입력 준비 후 저장소 루트에서 실행합니다. 아래 순서는 원본 실행 순서를 유지합니다.

```bash
python -X utf8 commute/scripts/03_gaps_and_shared.py
python -X utf8 commute/scripts/02_commute_access.py
python -X utf8 commute/scripts/04_gap_priority_commute.py
python -X utf8 commute/scripts/05_factory_distance.py
python -X utf8 commute/scripts/07_sensitivity.py
python -X utf8 commute/scripts/06_figures.py
```

`COMMUTE_OUT`으로 결과 폴더를 분리하고, 동일한 값을 각 단계에 적용할 수 있습니다. 그림 경로는 `COMMUTE_FIG`, 글꼴은 `COMMUTE_FONT`로 지정합니다. 기본 결과 폴더는 `commute/results/`이므로 재실행 전 결과를 별도 경로로 지정하면 제출 시점의 집계를 보존할 수 있습니다.

공개본에는 원자료·개별 지점 좌표가 포함되지 않아 전체 파이프라인의 독립 재현에는 제한이 있습니다. 코드 검토와 저장된 집계 열람, 합성 입력 테스트는 원자료 없이 가능합니다.
