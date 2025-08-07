# Database Migration and Testing

## Current Situation
- Need to migrate user table to add 'role' field
- Update all existing users to have 'user' role by default  
- Create new admin user with 'admin' role
- Update authentication middleware to check roles
- Write tests for role-based access control

## Acceptance Criteria
- Migration runs without data loss
- Existing functionality still works
- Admin routes are protected
- All tests pass