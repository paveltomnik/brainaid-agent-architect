# Contributing / Участие в разработке

1. Open an issue with the failure scenario and a minimal, **sanitized** reproducer. Never upload credentials, personal messages, private documents, customer data or real API tokens.
2. Changes to `scripts/` must be standard-library Python (3.10+) and offline by default. No telemetry or outbound network access.
3. Add positive/negative tests in `tests/`, update relevant documentation and changelog, run:
   ```bash
   python scripts/doctor.py
   python -m unittest discover -s tests -v
   python scripts/fault_lab.py --all
   python scripts/validate_spec.py examples/content_pipeline.json
   ```
4. Explain what a check **does not prove**. Audit findings should be labeled heuristic unless reproduced on the actual system.
5. In pull requests, describe changes, test output and security implications. Respect the MIT license.

Русский: сообщения об ошибках и PR на русском языке тоже приветствуются. Не публикуйте реальные ключи, приватный код заказчиков и персональные данные. Приложите минимальный обезличенный пример, ожидаемое и фактическое поведение, а также результаты тестов.
