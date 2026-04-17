#!/usr/bin/env python3
"""
A/B Test Management CLI

Simple command-line tool for creating and managing A/B tests.

Usage:
    python scripts/manage_ab_tests.py create --name "Model v2 Test" --variants '{"control": {"model_version": "1.0"}, "treatment": {"model_version": "2.0"}}' --split '{"control": 0.5, "treatment": 0.5}'
    python scripts/manage_ab_tests.py list
    python scripts/manage_ab_tests.py activate <test_id>
    python scripts/manage_ab_tests.py results <test_id>
    python scripts/manage_ab_tests.py complete <test_id>
"""

import sys
import os
import json
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from app.models import ABTest, ABTestEvent
from sqlalchemy import func


def create_test(args):
    """Create a new A/B test"""
    db = SessionLocal()
    
    try:
        variants = json.loads(args.variants)
        traffic_split = json.loads(args.split)
        
        # Validate
        if set(variants.keys()) != set(traffic_split.keys()):
            print("Error: Variants and traffic split keys must match")
            return
        
        total_split = sum(traffic_split.values())
        if not (0.99 <= total_split <= 1.01):
            print("Error: Traffic split must sum to 1.0")
            return
        
        # Create test
        test = ABTest(
            name=args.name,
            description=args.description,
            variants=json.dumps(variants),
            traffic_split=json.dumps(traffic_split),
            metrics=json.dumps(["accuracy", "latency", "confidence"]),
            status="draft",
        )
        
        db.add(test)
        db.commit()
        db.refresh(test)
        
        print(f"✓ Created A/B test: {test.name} (ID: {test.id})")
        print(f"  Status: {test.status}")
        print(f"  Variants: {list(variants.keys())}")
        print(f"  Split: {traffic_split}")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


def list_tests(args):
    """List all A/B tests"""
    db = SessionLocal()
    
    try:
        tests = db.query(ABTest).order_by(ABTest.created_at.desc()).all()
        
        if not tests:
            print("No A/B tests found")
            return
        
        print(f"\n{'ID':<5} {'Name':<30} {'Status':<12} {'Variants':<20} {'Created':<20}")
        print("-" * 90)
        
        for test in tests:
            variants = json.loads(test.variants)
            variant_names = ", ".join(variants.keys())
            created = test.created_at.strftime("%Y-%m-%d %H:%M")
            
            print(f"{test.id:<5} {test.name:<30} {test.status:<12} {variant_names:<20} {created:<20}")
        
        print()
        
    finally:
        db.close()


def activate_test(args):
    """Activate an A/B test"""
    db = SessionLocal()
    
    try:
        test = db.query(ABTest).filter(ABTest.id == args.test_id).first()
        
        if not test:
            print(f"Error: Test {args.test_id} not found")
            return
        
        if test.status == "active":
            print(f"Test '{test.name}' is already active")
            return
        
        test.status = "active"
        test.start_date = datetime.utcnow()
        test.updated_at = datetime.utcnow()
        
        db.commit()
        
        print(f"✓ Activated test: {test.name}")
        print(f"  Started: {test.start_date}")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


def show_results(args):
    """Show A/B test results"""
    db = SessionLocal()
    
    try:
        test = db.query(ABTest).filter(ABTest.id == args.test_id).first()
        
        if not test:
            print(f"Error: Test {args.test_id} not found")
            return
        
        print(f"\nA/B Test Results: {test.name}")
        print(f"Status: {test.status}")
        print(f"Started: {test.start_date}")
        print("-" * 80)
        
        variants = json.loads(test.variants)
        
        for variant_name in variants.keys():
            events = db.query(ABTestEvent).filter(
                ABTestEvent.test_id == test.id,
                ABTestEvent.variant == variant_name
            ).all()
            
            total_events = len(events)
            
            if total_events == 0:
                print(f"\n{variant_name.upper()}: No events yet")
                continue
            
            # Calculate metrics
            latencies = [e.latency_ms for e in events if e.latency_ms]
            confidences = [e.confidence for e in events if e.confidence]
            feedback_events = [e for e in events if e.accuracy is not None]
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            avg_accuracy = sum(e.accuracy for e in feedback_events) / len(feedback_events) if feedback_events else None
            
            print(f"\n{variant_name.upper()}:")
            print(f"  Total Events: {total_events}")
            print(f"  Avg Latency: {avg_latency:.0f}ms")
            print(f"  Avg Confidence: {avg_confidence:.3f}")
            if avg_accuracy is not None:
                print(f"  Avg Accuracy: {avg_accuracy:.3f} ({len(feedback_events)} feedback)")
            else:
                print(f"  Avg Accuracy: N/A (no feedback yet)")
        
        print()
        
    finally:
        db.close()


def complete_test(args):
    """Mark test as completed"""
    db = SessionLocal()
    
    try:
        test = db.query(ABTest).filter(ABTest.id == args.test_id).first()
        
        if not test:
            print(f"Error: Test {args.test_id} not found")
            return
        
        test.status = "completed"
        test.end_date = datetime.utcnow()
        test.updated_at = datetime.utcnow()
        
        db.commit()
        
        print(f"✓ Completed test: {test.name}")
        print(f"  Ended: {test.end_date}")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="A/B Test Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create new A/B test")
    create_parser.add_argument("--name", required=True, help="Test name")
    create_parser.add_argument("--description", help="Test description")
    create_parser.add_argument("--variants", required=True, help="Variants JSON")
    create_parser.add_argument("--split", required=True, help="Traffic split JSON")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all tests")
    
    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Activate a test")
    activate_parser.add_argument("test_id", type=int, help="Test ID")
    
    # Results command
    results_parser = subparsers.add_parser("results", help="Show test results")
    results_parser.add_argument("test_id", type=int, help="Test ID")
    
    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Mark test as completed")
    complete_parser.add_argument("test_id", type=int, help="Test ID")
    
    args = parser.parse_args()
    
    if args.command == "create":
        create_test(args)
    elif args.command == "list":
        list_tests(args)
    elif args.command == "activate":
        activate_test(args)
    elif args.command == "results":
        show_results(args)
    elif args.command == "complete":
        complete_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
