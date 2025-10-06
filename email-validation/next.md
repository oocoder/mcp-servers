Think this through,
Execute the following development cycle to implement and evaluate the latest recommendation.

## Core Tasks
1. **Checkpoint**: Save current state before changes
   ```bash
   git add . && git commit -m "Checkpoint: Pre-implementation state"
   ```
2. **Status Update**: Document concisely the current progress in `CLAUDE.md`
   - Include timestamp and brief description of changes being made
3. **Implementation**: Apply the recommended changes/improvements
   - **Project Setup**:
     - Create a main application file (e.g., `main.py`).
     - Initialize a virtual environment and install necessary libraries (`dnspython`).
   - **Syntax Validation**:
     - Implement a function `is_valid_syntax(email)` using regex to validate the basic email format.
   - **Domain/MX Record Validation**:
     - Implement a function `get_mx_record(domain)` to perform a DNS lookup for the mail exchanger (MX) record.
   - **SMTP Mailbox Verification**:
     - Implement a function `verify_mailbox(email, mx_server)` that connects to the mail server via SMTP and checks if the recipient mailbox exists without sending an email.
   - **API Server**:
     - Wrap the validation logic in a simple web server (e.g., using FastAPI or Flask) that exposes an endpoint (e.g., `/validate`) to accept and process email validation requests.

4. **Testing**: Verify implementation works correctly.
5. **Test-Driven/Behavior-Driven Development (TDD/BDD)**:
   - **Write a Failing Test**: Before each implementation step, create a test case that verifies the desired functionality.
     - Test for valid and invalid email syntax.
     - Test for domains with and without MX records.
     - Test for existing and non-existent mailboxes on a test mail server.
   - **Write Code to Pass the Test**: Implement the minimum amount of code necessary to make the failing test pass.
   - **Refactor**: Improve the code's structure and clarity while ensuring all tests still pass.
   - **Incorporate Negative Tests**: Add tests to verify that the system gracefully handles edge cases like timeouts, non-existent domains, and server connection errors.
   - **Incrementally Build**: Repeat the cycle for each feature: syntax check, MX lookup, and SMTP verification.

6. **Code Quality Audit**: As a software architect, ensure:
   - Code quality and maintainability.
   - Clear, useful comments explaining complex logic (e.g., SMTP interaction).
   - Remove redundancies and dead code.
   - Fix all type checking errors:
   ```bash
   pyright -p pyright_cli.json *.py
   ```
   - Clean up temporary files.

7. **Results Analysis**: Based on evaluation results, determine:
   - The accuracy of the validation for different email providers.
   - The system's performance and response time.
   - Next steps, such as handling catch-all domains or greylisting.

8. **Iterate**: If performance is unsatisfactory, repeat from step 2
   - Document what didn't work and why (e.g., "Initial SMTP connection timed out frequently; increasing timeout value.").
   - Adjust approach based on learnings.

9. **Documentation Update**:
   - Update `CLAUDE.md` with concise status and results.
   - Update `README.md` with a professional, concise project status, including API usage instructions.

10. **Final Checkpoint**: Commit completed work
    ```bash
    git add . && git commit -m "Implementation complete: Email validation server MVP"
    ```
