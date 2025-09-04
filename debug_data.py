#!/usr/bin/env python3
"""
Debug script to analyze the input data and identify potential scheduling issues.
"""

import csv
import os
from datetime import datetime
import re
from collections import defaultdict, Counter

def analyze_data():
    """Analyze the input data to understand scheduling constraints."""
    
    print("=== DATA ANALYSIS FOR SCHEDULING DEBUG ===\n")
    
    # Analyze applicants
    applicants_file = "inputs/applicant_information.csv"
    total_applicants = 0
    team_interests = Counter()
    availability_counts = Counter()
    
    with open(applicants_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            total_applicants += 1
            
            # Count team interests
            teams_str = row['Select the teams are you interested in joining:']
            if 'Astra' in teams_str:
                team_interests['Astra'] += 1
            if 'Juvo' in teams_str:
                team_interests['Juvo'] += 1
            if 'Infinitum' in teams_str:
                team_interests['Infinitum'] += 1
            if 'Terra' in teams_str:
                team_interests['Terra'] += 1
                
            # Count availability slots per applicant
            availability_count = 0
            date_columns = [
                'Thursday, September 11, 2025',
                'Friday, September 12, 2025', 
                'Saturday, September 13, 2025',
                'Sunday, September 14, 2025',
                'Monday, September 15, 2025'
            ]
            
            for date_col in date_columns:
                if date_col in row and row[date_col]:
                    slots = row[date_col].split(',')
                    availability_count += len(slots)
            
            availability_counts[availability_count] += 1
    
    print(f"APPLICANTS: {total_applicants}")
    print(f"Team interests: {dict(team_interests)}")
    print(f"Availability distribution: {dict(sorted(availability_counts.items()))}")
    print()
    
    # Analyze recruiters
    recruiters_file = "inputs/recruiters.csv"
    total_recruiters = 0
    recruiter_teams = Counter()
    recruiter_availability = defaultdict(int)
    
    with open(recruiters_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            total_recruiters += 1
            team = row['team']
            recruiter_teams[team] += 1
            
            # Count availability periods
            if row['availability']:
                periods = row['availability'].split(';')
                recruiter_availability[len(periods)] += 1
    
    print(f"RECRUITERS: {total_recruiters}")
    print(f"Team distribution: {dict(recruiter_teams)}")
    print(f"Availability periods: {dict(sorted(recruiter_availability.items()))}")
    print()
    
    # Analyze rooms
    rooms_file = "inputs/rooms.csv"
    total_rooms = 0
    
    with open(rooms_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            total_rooms += 1
    
    print(f"ROOMS: {total_rooms}")
    print()
    
    # Calculate theoretical requirements
    print("=== THEORETICAL REQUIREMENTS ===")
    print(f"Total interviews needed: {total_applicants * 2} ({total_applicants} group + {total_applicants} individual)")
    print(f"Group interviews needed: ~{total_applicants // 6} (assuming 6 applicants per group)")
    print(f"Individual interviews needed: {total_applicants}")
    print()
    
    # Calculate time slot capacity
    # Time slots available: 
    # Sep 11, 12, 15: 4 hours each = 12 hours total = 36 slots (20min each)
    # Sep 13, 14: 12 hours each = 24 hours total = 72 slots
    # Total: 108 slots
    evening_slots = 3 * 12  # 3 days × 4 hours × 3 slots per hour
    weekend_slots = 2 * 36  # 2 days × 12 hours × 3 slots per hour
    total_slots = evening_slots + weekend_slots
    
    print(f"=== TIME SLOT CAPACITY ===")
    print(f"Evening slots (Sep 11,12,15): {evening_slots}")
    print(f"Weekend slots (Sep 13,14): {weekend_slots}")
    print(f"Total 20-minute slots: {total_slots}")
    print()
    
    # Calculate capacity
    group_capacity = total_slots * total_rooms  # Each slot can have 1 group interview per room
    individual_capacity = total_slots * total_rooms  # Each slot can have 1 individual interview per room
    
    print(f"=== CAPACITY ANALYSIS ===")
    print(f"Theoretical group interview capacity: {group_capacity} room-slots")
    print(f"Theoretical individual interview capacity: {individual_capacity} room-slots")
    print(f"Group interviews needed: ~{total_applicants // 6}")
    print(f"Individual interviews needed: {total_applicants}")
    print()
    
    # Check if theoretically possible
    group_feasible = (total_applicants // 6) <= group_capacity
    individual_feasible = total_applicants <= individual_capacity
    
    print(f"=== FEASIBILITY CHECK ===")
    print(f"Group interviews feasible: {group_feasible}")
    print(f"Individual interviews feasible: {individual_feasible}")
    
    if group_feasible and individual_feasible:
        print("✓ Scheduling should be theoretically possible")
    else:
        print("✗ Scheduling may not be possible due to capacity constraints")
        
    print()
    
    # Recommendations
    print("=== RECOMMENDATIONS ===")
    if total_applicants // 6 > 20:
        print("- Consider larger group sizes (7-8 applicants per group)")
    if recruiter_teams['All'] < 4:
        print("- Consider adding more 'All' team recruiters for flexibility")
    if total_recruiters < 16:
        print("- May need more recruiters for simultaneous group interviews")
        
    print("- Try reducing time proximity constraints")
    print("- Consider longer time windows")

if __name__ == "__main__":
    analyze_data()
