# Running the scheduler on Windows

The scheduler sends every automatic mail (the Birthday Mailer today, more later) every 30 minutes by default (at :00 and :30); `SCHEDULER_INTERVAL_MINUTES` in the `.env` changes that (5, 10, 15, 20, 30 or 60). Run **one** of these on the server:

| | How | When to choose it |
|---|---|---|
| **Windows service** (recommended) | `install_scheduler_service.ps1` (needs [NSSM](https://nssm.cc), a free single file) | It restarts itself after a crash, and the Scheduled Mails page shows when it last ran. |
| **Scheduled task** | `register_scheduler_task.ps1` (nothing to install; `-EveryMinutes` must match the `.env`) | If you would rather not install NSSM. |

Both read the same `.env` as the web application. Do not run both at once; if two copies do run, a lock makes the second one skip, so no mail is sent twice.

After installing: open **Admin > Scheduled Mails**. It should say "The scheduler is running". If it says it has not run for longer than its interval plus 15 minutes, the service or the task is not running.
Logs: `backend\logs\scheduler-<date>.log` (every run), `automation_errors-<date>.log` (every error with its reason), `service.out.log` / `service.err.log`.

To try it by hand, in the backend folder: `python manage.py run_scheduler --once` (one run) or `python manage.py run_scheduler --status`.
