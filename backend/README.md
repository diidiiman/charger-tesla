# Backend Testing and Development Guide

## Architecture
The backend is structured into **Routes** and **Use Cases**.

1. **Routes (`app/routes/`)**: Should contain almost no business logic. They should extract parameters, authenticate the user, and pass the required context directly into a Use Case.
2. **Use Cases (`app/use_cases/`)**: Must be single-purpose classes or modules. The entry point is the `call()` method. All core logic, validation, third-party API calls, and database operations belong here.

Example:
```python
class DoSomethingUseCase:
    async def call(self, db: AsyncSession, user: User, param: str) -> Result:
        # business logic here
        return Result(...)
```

## Testing
1. **Mirror File Structure**: The `tests/` directory must mirror `app/`. 
   - `app/use_cases/foo/bar.py` -> `tests/use_cases/foo/test_bar.py`
   - `app/routes/foo.py` -> `tests/routes/test_foo_routes.py`
2. **Pytest**: We use `pytest` with `pytest-asyncio`. 
3. **Mocks**: Use `pytest-mock` (e.g. `mocker.patch(...)`) or `unittest.mock.patch` for any third-party API calls (e.g., Tesla API, Nord Pool API) or push notifications.
4. **Factories**: Use `factory-boy` to generate fake database objects. Factories are located in `tests/factories/` (e.g., `tests/factories/user_factory.py`). Avoid creating objects manually using `User(...)` in tests.
5. **Coverage**: Test both the route output and the underlying use case behavior.

## AI Instructions
Whenever the AI is tasked with backend modifications, it MUST follow these steps:
1. Implement the requested business logic inside a tightly scoped Use Case in `app/use_cases/`.
2. Update the corresponding Route in `app/routes/` to invoke `.call(...)` on the Use Case.
3. If database schema changes are required, generate a migration using `docker compose exec backend alembic revision --autogenerate -m "Description"`. The migration file and revision ID will automatically use sequential integers (e.g. `0009_...`).
4. Write or update corresponding Pytest tests covering the Use Case, using Mocks where necessary and Factories for database models.
5. Write or update Pytest tests covering the Route itself to verify status codes and payloads.
6. Once all code is written, format it using `black`: `docker compose exec backend black .`
7. Run the tests and ensure they pass: `docker compose exec backend pytest`
