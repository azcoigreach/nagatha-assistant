-- Initialize the database with any required extensions or setup
-- This script runs when the PostgreSQL container is first created

-- Create database if it doesn't exist (this is handled by POSTGRES_DB env var)
-- But we can add any additional setup here

-- Enable UUID extension for Django UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes that might be useful for the application
-- These will be created by Django migrations, but we can add database-specific optimizations here

-- Log the initialization
DO $$
BEGIN
    RAISE NOTICE 'Nagatha Dashboard database initialized successfully';
END $$;