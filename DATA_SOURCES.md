# 데이터 출처와 공개 범위

아래는 제출 분석판에서 사용한 자료입니다. 원자료의 배포 권한을 이 저장소가 대신 부여하지 않습니다.

| 자료 | 기준 | 출처 |
|---|---|---|
| 화성시 자전거 노선·도로면 | 2026-09 수집 | [화성시 생활공간 웹포털](https://air.hscity.go.kr/hsgisMap) |
| 자전거 시설·도로망 | 2026-09 추출 | [OpenStreetMap](https://www.openstreetmap.org/copyright), © OpenStreetMap contributors |
| 공장등록 현황 | 2024-02 | [화성시청](https://www.hscity.go.kr) |
| 공장 주소 좌표 변환 | 분석 당시 캐시 | [브이월드](https://www.vworld.kr) |
| 통근 수단 | 인구총조사 2020·2015 | [KOSIS](https://kosis.kr), [상세 출처](commute/data/통근수단_출처.md) |
| 행정동별 주민등록 인구 | 2026-08 | [행정안전부·공공데이터포털](https://www.data.go.kr/data/15097972/fileData.do) |
| 100m 인구 격자 | GHS-POP R2023A | [EU JRC GHSL](https://human-settlement.emergency.copernicus.eu/), CC BY 4.0 |
| 행정동 경계 | 2026-07 | [SGIS·vuski/admdongkor](https://github.com/vuski/admdongkor) |

GHSL: Schiavina, M., Freire, S., Carioli, A., MacManus, K. (2023), GHS-POP R2023A, European Commission JRC, DOI: 10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE.

공개본에는 코드, 테스트, 데이터 수집 명세, 행정구역 단위 집계와 연결 묶음의 합계만 포함합니다. 공장 연락처·주소 원본, 지오코딩 캐시, 수동 보정 좌표, GIS 원자료, 개별 연결 후보 좌표, 비공개 지도·릴리스·세션 기록은 포함하지 않습니다. 원자료 재배포 조건을 확인하지 않은 상태에서 비공개 작업 저장소의 이력을 공개하지 않았습니다.

파일별 원본 해시는 `SOURCE_SNAPSHOT.json`, 원자료 명세는 `data_manifest.json`에서 확인할 수 있습니다.
