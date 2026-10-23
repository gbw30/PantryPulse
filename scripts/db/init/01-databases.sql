-- Runs once on first container start. pantrypulse_dev is created by POSTGRES_DB.
-- Integration pair (3000/8000) uses pantrypulse_dev; tests use pantrypulse_test;
-- each builder lane gets its own database (TASK-PROTOCOL worktree strategy).
CREATE DATABASE pantrypulse_test;
CREATE DATABASE pantrypulse_lane1;
CREATE DATABASE pantrypulse_lane2;
CREATE DATABASE pantrypulse_lane3;
