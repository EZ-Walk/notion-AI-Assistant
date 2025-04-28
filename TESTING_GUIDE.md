# Notion Comments Testing Guide

## 1. Testing Strategy Overview

Focus on the five phases of the webhook processing pipeline:
- **EVENT_VERIFICATION**: Initial validation of webhook payloads
- **EVENT_ROUTING**: Routing events to appropriate handlers
- **CONTEXT_COLLECTION**: Retrieving user tokens and comment data
- **LANGGRAPH_INVOCATION**: Processing comments with AI
- **RESPONSE_ANALYSIS**: Creating replies and tracking token usage

## 2. Testing Environment Setup

- Install dependencies: `pip install pytest pytest-flask pytest-mock pytest-cov`
- Create test directory structure:
  ```
  tests/
  ├── conftest.py        # Shared fixtures
  ├── unit/             # Unit tests
  ├── integration/      # Integration tests
  └── e2e/              # End-to-end tests
  ```
- Configure pytest.ini for consistent test discovery and execution

## 3. Core Testing Principles

1. **Use Real Supabase Instances**: Test with actual database instances instead of mocks
2. **Mock External Services**: Use mocks for Notion API and LangGraph
3. **Cover All Phases**: Ensure each pipeline phase has dedicated tests
4. **Test Error Scenarios**: Validate error handling throughout the pipeline

## 4. Fixture Strategy

1. **Flask Client**: For simulating HTTP requests
2. **Webhook Payloads**: Various sample payloads for different scenarios
3. **Local Supabase**: Docker-based Supabase instance with mirrored schema
4. **Mocked Notion API**: Simulated API responses
5. **Mocked LangGraph**: Simulated AI processing

## 5. Testing Each Pipeline Phase

### Unit Testing
- **EVENT_VERIFICATION**: Test challenge responses and input validation
- **EVENT_ROUTING**: Test correct routing based on event type
- **CONTEXT_COLLECTION**: Test token retrieval and error handling
- **LANGGRAPH_INVOCATION**: Test AI processing and error scenarios
- **RESPONSE_ANALYSIS**: Test reply creation and usage tracking

### Integration Testing
- Test interactions between phases
- Verify data flow through multiple components
- Use real Supabase with mocked external services

### End-to-End Testing
- Use Docker-based environment with all services
- Test complete webhook processing flow
- Verify database writes and process completion

## 6. Supabase Integration Testing Strategy

1. **Docker Setup**: Run Supabase locally using Docker
2. **Schema Migration**: Apply production schema to test database
3. **Test User Creation**: Create test accounts for validation
4. **Direct DB Verification**: Check records directly in database
5. **Cleanup**: Remove test data after tests complete

## 7. Mocking External Services

### Notion API
- Mock comment retrieval responses
- Mock comment creation responses
- Mock comment update responses
- Mock webhook events
- **Special Cases**:
  - Bot-authored comments (should be ignored)
  - Very long comments

### LangGraph
- Mock AI processing with predetermined responses
- Simulate processing errors

## 8. Continuous Integration

- Configure GitHub Actions for automated testing
- Run tests on push/PR to maintain quality
- Generate coverage reports to identify gaps

## 9. Implementation Plan

1. Start with unit tests for core functionality
2. Set up Supabase test environment
3. Implement integration tests for key workflows
4. Create Docker-based end-to-end test suite
5. Configure CI/CD pipeline

## 10. Best Practices

- Keep tests independent and idempotent
- Use realistic test data
- Clean up after tests complete
- Focus on boundary conditions and edge cases
- Monitor test performance and coverage
