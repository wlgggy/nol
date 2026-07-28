# NOL Auto Assign Helper

This is a local-only Chrome automation script for the current Windows environment.

## Files

- `seat_select_macro.py`: Connects to a Chrome tab through Chrome DevTools and runs the seat auto-assign flow.

## Requirements

- Windows
- Python 3
- Google Chrome
- Chrome opened with remote debugging enabled

No external Python packages are required.

## How to Run

Open Chrome in remote debugging mode:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\chrome-debug"
```

In that Chrome window, go to the NOL seat selection page.

Then run:

```powershell
cd C:\Users\User\Desktop\test
python seat_select_macro.py
```

## Current Behavior

- Looks for the `중립구역` seat grade.
- Stops immediately if its remaining count is `0`.
- If seats remain, clicks `중립구역`.
- Clicks `자동 배정받기`.
- In the seat count sheet, clicks `+`.
- Clicks `선택 완료`.
- Repeats until `좌석 1개가 자동 배정됐어요` appears.
- If one full attempt fails, clicks the seat-plan fit button before retrying.
- Stops after 3 auto-assign attempts.

Stop manually with `Ctrl+C`.
