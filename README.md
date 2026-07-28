# NOL 자동 배정 도우미

현재 Windows 환경에서만 사용하기 위해 만든 로컬용 Chrome 자동화 스크립트입니다.

## 파일

- `seat_select_macro.py`: Chrome DevTools에 연결해서 좌석 자동 배정 흐름을 실행합니다.

## 필요 환경

- Windows
- Python 3
- Google Chrome
- 원격 디버깅 모드로 실행한 Chrome

외부 Python 패키지는 필요하지 않습니다.

## 실행 방법

먼저 Chrome을 원격 디버깅 모드로 실행합니다.

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\chrome-debug"
```

열린 Chrome 창에서 NOL 좌석 선택 화면까지 이동합니다.

그 다음 PowerShell에서 실행합니다.

```powershell
cd C:\Users\User\Desktop\test
python seat_select_macro.py
```

## 동작 방식

- `중립구역` 좌석 등급을 찾습니다.
- 잔여 수량이 `0`이어도 종료하지 않고 계속 실행합니다.
- `중립구역`을 클릭합니다.
- `자동 배정받기` 버튼을 클릭합니다.
- 수량 선택 창에서 `+` 버튼을 클릭합니다.
- `선택 완료` 버튼을 클릭합니다.
- `좌석 1개가 자동 배정됐어요` 문구가 뜨면 종료합니다.
- 자동 배정에 실패하면 좌석도 전체보기 버튼을 누른 뒤 다시 시도합니다.
- 자동 배정 시도는 최대 3회까지만 실행합니다.

중단하려면 PowerShell에서 `Ctrl+C`를 누릅니다.
