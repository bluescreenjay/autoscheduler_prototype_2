#!/usr/bin/env python3

import csv
import datetime
from collections import defaultdict, Counter
import sys
import os
import glob
import pandas as pd

def get_latest_run_directory():
    """Find the most recent run directory"""
    run_pattern = "results/run_*"
    run_dirs = glob.glob(run_pattern)
    
    if not run_dirs:
        print("Error: No run directories found in results/")
        print("Make sure you've run the autoscheduler first.")
        sys.exit(1)
    
    # Sort by directory name (which includes timestamp) to get latest
    latest_run = sorted(run_dirs)[-1]
    print(f"Analyzing latest run: {latest_run}")
    return latest_run

def parse_time(time_str):
    """Parse time string into datetime object"""
    return datetime.datetime.strptime(time_str, "%m/%d/%Y %I:%M %p")

def load_recruiter_teams():
    """Load recruiter team affiliations"""
    recruiter_teams = {}
    with open('inputs/recruiters.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            recruiter_teams[row['recruiter_name']] = row['team']
    return recruiter_teams

def load_applicant_teams():
    """Load applicant team preferences"""
    applicant_teams = {}
    with open('inputs/applicant_information.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['First and Last Name']
            teams = row['Select the teams are you interested in joining:']
            applicant_teams[name] = teams
    return applicant_teams

def analyze_schedule():
    """Comprehensive analysis of the scheduling results"""
    
    # Find the latest run directory
    latest_run_dir = get_latest_run_directory()
    
    # Load supporting data
    recruiter_teams = load_recruiter_teams()
    applicant_teams = load_applicant_teams()
    
    # Load original data files for availability checking
    try:
        applicants_df = pd.read_csv('inputs/applicant_information.csv')
        recruiters_df = pd.read_csv('inputs/recruiters.csv')
        schedule_df = pd.read_csv(os.path.join(latest_run_dir, 'main_schedule.csv'))
        schedule_df['Start Time'] = pd.to_datetime(schedule_df['Start Time'])
        schedule_df['End Time'] = pd.to_datetime(schedule_df['End Time'])
    except FileNotFoundError as e:
        print(f"Error loading data files: {e}")
        print("Make sure the input files are in the inputs/ directory")
        applicants_df = None
        recruiters_df = None
        schedule_df = None
    
    # Data structures for analysis
    applicant_interviews = defaultdict(list)
    room_schedules = defaultdict(list)
    individual_team_matches = []
    group_team_diversity = []
    
    print("=== COMPREHENSIVE SCHEDULE ANALYSIS ===")
    print(f"Run Directory: {latest_run_dir}")
    print()
    
    # Process main schedule
    schedule_file = os.path.join(latest_run_dir, 'main_schedule.csv')
    if not os.path.exists(schedule_file):
        print(f"Error: Schedule file not found at {schedule_file}")
        sys.exit(1)
    
    with open(schedule_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            interview_type = row['Type']
            start_time = parse_time(row['Start Time'])
            end_time = parse_time(row['End Time'])
            room = row['Room']
            applicants = [name.strip() for name in row['Applicants'].split(';')]
            recruiters = [name.strip() for name in row['Recruiters'].split(';')]
            
            # Track applicant interviews
            for applicant in applicants:
                applicant_interviews[applicant].append({
                    'type': interview_type,
                    'start': start_time,
                    'end': end_time,
                    'room': room,
                    'recruiters': recruiters
                })
            
            # Track room usage
            room_schedules[room].append({
                'start': start_time,
                'end': end_time,
                'type': interview_type,
                'applicants': applicants,
                'recruiters': recruiters
            })
            
            # Analyze individual interviews for team matching
            if interview_type == 'individual':
                applicant = applicants[0]
                recruiter = recruiters[0]
                applicant_preferred_teams = applicant_teams.get(applicant, "")
                recruiter_team = recruiter_teams.get(recruiter, "Unknown")
                
                # Check if recruiter's team matches applicant's preferences
                match = recruiter_team in applicant_preferred_teams or recruiter_team == "All"
                individual_team_matches.append({
                    'applicant': applicant,
                    'recruiter': recruiter,
                    'recruiter_team': recruiter_team,
                    'applicant_teams': applicant_preferred_teams,
                    'match': match
                })
            
            # Analyze group interviews for team diversity
            elif interview_type == 'group':
                recruiter_team_set = set()
                for recruiter in recruiters:
                    team = recruiter_teams.get(recruiter, "Unknown")
                    if team != "All":  # Don't count "All" as a specific team
                        recruiter_team_set.add(team)
                
                group_team_diversity.append({
                    'recruiters': recruiters,
                    'teams': list(recruiter_team_set),
                    'team_count': len(recruiter_team_set),
                    'applicants': applicants
                })

    # ANALYSIS 1: Check if every applicant is fully scheduled
    print("1. APPLICANT SCHEDULING COMPLETENESS:")
    print("=" * 50)
    
    fully_scheduled = 0
    partially_scheduled = 0
    unscheduled = 0
    
    for applicant, interviews in applicant_interviews.items():
        has_group = any(interview['type'] == 'group' for interview in interviews)
        has_individual = any(interview['type'] == 'individual' for interview in interviews)
        
        if has_group and has_individual:
            fully_scheduled += 1
        elif has_group or has_individual:
            partially_scheduled += 1
            print(f"  PARTIALLY SCHEDULED: {applicant}")
            print(f"    Group: {'Yes' if has_group else 'No'}")
            print(f"    Individual: {'Yes' if has_individual else 'No'}")
        else:
            unscheduled += 1
            print(f"  UNSCHEDULED: {applicant}")
    
    total_applicants = len(applicant_interviews)
    print(f"\nSUMMARY:")
    print(f"  Total applicants: {total_applicants}")
    print(f"  Fully scheduled: {fully_scheduled} ({fully_scheduled/total_applicants*100:.1f}%)")
    print(f"  Partially scheduled: {partially_scheduled} ({partially_scheduled/total_applicants*100:.1f}%)")
    print(f"  Unscheduled: {unscheduled} ({unscheduled/total_applicants*100:.1f}%)")
    
    # ANALYSIS 2: Individual interview team matching
    print(f"\n2. INDIVIDUAL INTERVIEW TEAM MATCHING:")
    print("=" * 50)
    
    matches = sum(1 for match in individual_team_matches if match['match'])
    total_individual = len(individual_team_matches)
    match_percentage = matches / total_individual * 100 if total_individual > 0 else 0
    
    print(f"Team preference matches: {matches}/{total_individual} ({match_percentage:.1f}%)")
    print(f"\nSample mismatches (first 5):")
    mismatches = [match for match in individual_team_matches if not match['match']]
    for i, mismatch in enumerate(mismatches[:5]):
        print(f"  {mismatch['applicant']} -> {mismatch['recruiter']} ({mismatch['recruiter_team']})")
        print(f"    Applicant prefers: {mismatch['applicant_teams']}")
    
    if len(mismatches) > 5:
        print(f"  ... and {len(mismatches) - 5} more mismatches")
    
    # ANALYSIS 3: Room conflict detection
    print(f"\n3. ROOM CONFLICT ANALYSIS:")
    print("=" * 50)
    
    conflicts_found = 0
    for room, schedule in room_schedules.items():
        # Sort interviews by start time
        schedule.sort(key=lambda x: x['start'])
        
        for i in range(len(schedule) - 1):
            current = schedule[i]
            next_interview = schedule[i + 1]
            
            # Check for overlap
            if current['end'] > next_interview['start']:
                conflicts_found += 1
                print(f"  CONFLICT in {room}:")
                print(f"    {current['start'].strftime('%m/%d %I:%M %p')} - {current['end'].strftime('%I:%M %p')}: {current['type']}")
                print(f"    {next_interview['start'].strftime('%m/%d %I:%M %p')} - {next_interview['end'].strftime('%I:%M %p')}: {next_interview['type']}")
                print(f"    Overlap: {(current['end'] - next_interview['start']).total_seconds() / 60:.0f} minutes")
    
    if conflicts_found == 0:
        print("  ✓ No room conflicts detected!")
    else:
        print(f"  ✗ {conflicts_found} room conflicts found!")
    
    # ANALYSIS 4: Group interview team diversity
    print(f"\n4. GROUP INTERVIEW TEAM DIVERSITY:")
    print("=" * 50)
    
    team_diversity_stats = Counter()
    for group in group_team_diversity:
        team_diversity_stats[group['team_count']] += 1
    
    print("Team diversity distribution:")
    for team_count in sorted(team_diversity_stats.keys()):
        count = team_diversity_stats[team_count]
        print(f"  {team_count} different teams: {count} group interviews")
    
    # Show examples of good diversity
    diverse_groups = [g for g in group_team_diversity if g['team_count'] >= 3]
    if diverse_groups:
        print(f"\nSample diverse groups (first 3):")
        for i, group in enumerate(diverse_groups[:3]):
            print(f"  Group {i+1}: {group['teams']} ({group['team_count']} teams)")
            print(f"    Recruiters: {', '.join(group['recruiters'])}")
    
    # ANALYSIS 5: Interview spacing analysis
    print(f"\n5. INTERVIEW SPACING ANALYSIS:")
    print("=" * 50)
    
    spacing_violations = 0
    overlap_violations = 0
    spacing_stats = []
    overlap_cases = []
    zero_gap_cases = []
    
    for applicant, interviews in applicant_interviews.items():
        if len(interviews) >= 2:
            # Sort interviews by time
            interviews.sort(key=lambda x: x['start'])
            
            # Calculate spacing between consecutive interviews
            for i in range(len(interviews) - 1):
                current = interviews[i]
                next_interview = interviews[i + 1]
                
                # Calculate gap between end of current and start of next
                gap_minutes = (next_interview['start'] - current['end']).total_seconds() / 60
                spacing_stats.append(gap_minutes)
                
                # Check for overlaps (negative gap)
                if gap_minutes < 0:
                    overlap_violations += 1
                    overlap_cases.append({
                        'applicant': applicant,
                        'gap': gap_minutes,
                        'current': current,
                        'next': next_interview
                    })
                    print(f"  OVERLAP VIOLATION: {applicant}")
                    print(f"    Overlap: {abs(gap_minutes):.0f} minutes")
                    print(f"    Interview 1: {current['start'].strftime('%m/%d %I:%M %p')} - {current['end'].strftime('%I:%M %p')} ({current['type']})")
                    print(f"    Interview 2: {next_interview['start'].strftime('%m/%d %I:%M %p')} - {next_interview['end'].strftime('%I:%M %p')} ({next_interview['type']})")
                
                # Check for zero gap (back-to-back)
                elif gap_minutes == 0:
                    zero_gap_cases.append({
                        'applicant': applicant,
                        'current': current,
                        'next': next_interview
                    })
                
                # Check for 90-minute constraint violation (but not overlaps)
                elif gap_minutes > 90:
                    spacing_violations += 1
                    print(f"  SPACING VIOLATION: {applicant}")
                    print(f"    Gap: {gap_minutes:.0f} minutes (exceeds 90-minute limit)")
                    print(f"    Interview 1: {current['start'].strftime('%m/%d %I:%M %p')} - {current['end'].strftime('%I:%M %p')}")
                    print(f"    Interview 2: {next_interview['start'].strftime('%m/%d %I:%M %p')} - {next_interview['end'].strftime('%I:%M %p')}")
    
    # Summary of constraint compliance
    if overlap_violations == 0 and spacing_violations == 0:
        print("  ✓ All interviews comply with timing constraints!")
        print(f"    - No overlapping interviews for same applicant")
        print(f"    - All gaps are ≤ 90 minutes")
    else:
        if overlap_violations > 0:
            print(f"  ✗ {overlap_violations} OVERLAP violations found (same applicant in multiple places at once)!")
        if spacing_violations > 0:
            print(f"  ✗ {spacing_violations} spacing constraint violations found (gap > 90 minutes)!")
    
    # Report zero-gap cases
    if zero_gap_cases:
        print(f"\n  Back-to-back interviews (0-minute gap): {len(zero_gap_cases)} cases")
        print(f"  Sample back-to-back cases (first 3):")
        for i, case in enumerate(zero_gap_cases[:3]):
            print(f"    {case['applicant']}: {case['current']['type']} ends {case['current']['end'].strftime('%I:%M %p')}, {case['next']['type']} starts {case['next']['start'].strftime('%I:%M %p')}")
    
    # Spacing statistics
    if spacing_stats:
        # Separate positive and negative gaps for clearer analysis
        positive_gaps = [gap for gap in spacing_stats if gap >= 0]
        negative_gaps = [gap for gap in spacing_stats if gap < 0]
        
        print(f"\nSpacing statistics:")
        print(f"  Total interview pairs analyzed: {len(spacing_stats)}")
        
        if negative_gaps:
            print(f"  Overlapping pairs: {len(negative_gaps)}")
            print(f"  Average overlap: {abs(sum(negative_gaps) / len(negative_gaps)):.1f} minutes")
            print(f"  Worst overlap: {abs(min(negative_gaps)):.1f} minutes")
        
        if positive_gaps:
            avg_spacing = sum(positive_gaps) / len(positive_gaps)
            min_spacing = min(positive_gaps)
            max_spacing = max(positive_gaps)
            
            print(f"  Non-overlapping pairs: {len(positive_gaps)}")
            print(f"  Average gap: {avg_spacing:.1f} minutes")
            print(f"  Minimum gap: {min_spacing:.1f} minutes")
            print(f"  Maximum gap: {max_spacing:.1f} minutes")
    
    # ANALYSIS 6: Availability compliance
    print(f"\n6. AVAILABILITY COMPLIANCE ANALYSIS:")
    print("=" * 50)
    
    if applicants_df is not None and recruiters_df is not None and schedule_df is not None:
        violations = []
        
        # Check applicant availability
        for applicant_name, interviews in applicant_interviews.items():
            for interview in interviews:
                # Find applicant data (strip whitespace for matching)
                applicant_name_clean = applicant_name.strip()
                applicant_data = applicants_df[applicants_df['First and Last Name'].str.strip() == applicant_name_clean]
                if applicant_data.empty:
                    violations.append(f"Applicant '{applicant_name}' not found in applicant data")
                    continue
                    
                applicant_data = applicant_data.iloc[0]
                
                # Check if applicant is available during this time
                available = False
                for col in applicant_data.index:
                    if col.startswith('2025-') or 'September' in col:  # Date columns
                        time_slots = str(applicant_data[col])
                        if pd.isna(applicant_data[col]) or time_slots == 'nan':
                            continue
                            
                        # Parse availability slots for this date
                        try:
                            interview_date = interview['start'].date()
                            
                            # Try different date formats
                            if col.startswith('2025-'):
                                col_date = pd.to_datetime(col).date()
                            else:
                                # Handle "Monday, September 15, 2025" format
                                col_date = pd.to_datetime(col).date()
                            
                            if interview_date == col_date:
                                # Check if interview time overlaps with any availability slot
                                if check_time_overlap(time_slots, interview['start'], interview['end']):
                                    available = True
                                    break
                        except:
                            continue
                
                if not available:
                    violations.append(f"APPLICANT UNAVAILABLE: {applicant_name} scheduled {interview['start'].strftime('%m/%d %I:%M %p')}-{interview['end'].strftime('%I:%M %p')} but not available")
        
        # Check recruiter availability for individual interviews
        individual_interviews = schedule_df[schedule_df['Type'] == 'individual']
        for _, interview in individual_interviews.iterrows():
            recruiter_name = interview['Recruiters']  # Single recruiter for individual
            start_time = interview['Start Time']
            end_time = interview['End Time']
            
            recruiter_data = recruiters_df[recruiters_df['recruiter_name'] == recruiter_name]
            if recruiter_data.empty:
                violations.append(f"Recruiter '{recruiter_name}' not found in recruiter data")
                continue
                
            recruiter_data = recruiter_data.iloc[0]
            availability_str = recruiter_data['availability']
            
            # Check if recruiter is available during this time
            if not check_recruiter_availability(availability_str, start_time, end_time):
                violations.append(f"RECRUITER UNAVAILABLE: {recruiter_name} scheduled {start_time.strftime('%m/%d %I:%M %p')}-{end_time.strftime('%I:%M %p')} but not available")
        
        # Check recruiter availability for group interviews
        group_interviews = schedule_df[schedule_df['Type'] == 'group']
        for _, interview in group_interviews.iterrows():
            # For group interviews, recruiters are separated by '; ' not ', '
            recruiters_str = interview['Recruiters']
            if '; ' in recruiters_str:
                recruiters = recruiters_str.split('; ')
            else:
                recruiters = recruiters_str.split(', ')
            
            start_time = interview['Start Time']
            end_time = interview['End Time']
            
            for recruiter_name in recruiters:
                recruiter_name = recruiter_name.strip()
                recruiter_data = recruiters_df[recruiters_df['recruiter_name'] == recruiter_name]
                if recruiter_data.empty:
                    violations.append(f"Recruiter '{recruiter_name}' not found in recruiter data")
                    continue
                    
                recruiter_data = recruiter_data.iloc[0]
                availability_str = recruiter_data['availability']
                
                # Check if recruiter is available during this time
                if not check_recruiter_availability(availability_str, start_time, end_time):
                    violations.append(f"RECRUITER UNAVAILABLE: {recruiter_name} scheduled {start_time.strftime('%m/%d %I:%M %p')}-{end_time.strftime('%I:%M %p')} but not available")
        
        # Report results
        if violations:
            print(f"  ✗ {len(violations)} availability violations found!")
            print("\n  Sample violations (first 10):")
            for i, violation in enumerate(violations[:10]):
                print(f"    {violation}")
            if len(violations) > 10:
                print(f"    ... and {len(violations) - 10} more violations")
        else:
            print("  ✓ All scheduled interviews match participant availability!")
    else:
        print("  ⚠ Cannot check availability - input data files not found")

def check_time_overlap(availability_str, interview_start, interview_end):
    """Check if interview time overlaps with any availability slot."""
    if pd.isna(availability_str) or availability_str == 'nan':
        return False
        
    # Parse availability string (e.g., "5:00 PM-6:00 PM, 7:00 PM-8:00 PM")
    time_ranges = str(availability_str).split(',')
    interview_date = interview_start.date()
    
    for time_range in time_ranges:
        time_range = time_range.strip()
        if '-' not in time_range:
            continue
            
        try:
            start_str, end_str = time_range.split('-')
            start_str = start_str.strip()
            end_str = end_str.strip()
            
            # Parse times and combine with interview date
            avail_start = pd.to_datetime(f"{interview_date} {start_str}")
            avail_end = pd.to_datetime(f"{interview_date} {end_str}")
            
            # Check for overlap
            if (interview_start < avail_end) and (interview_end > avail_start):
                return True
                
        except Exception as e:
            continue
    
    return False

def check_recruiter_availability(availability_str, interview_start, interview_end):
    """Check if recruiter is available during interview time."""
    if pd.isna(availability_str) or availability_str == 'nan':
        return False
    
    # Parse recruiter availability string (e.g., "2025-09-11 17:00-21:00;2025-09-12 17:00-21:00")
    time_ranges = str(availability_str).split(';')
    
    for time_range in time_ranges:
        time_range = time_range.strip()
        if ' ' not in time_range or '-' not in time_range:
            continue
            
        try:
            # Split date and time range
            date_part, time_part = time_range.split(' ', 1)
            start_time_str, end_time_str = time_part.split('-')
            
            # Parse datetime objects
            avail_start = pd.to_datetime(f"{date_part} {start_time_str}")
            avail_end = pd.to_datetime(f"{date_part} {end_time_str}")
            
            # Check for overlap
            if (interview_start < avail_end) and (interview_end > avail_start):
                return True
                
        except Exception as e:
            continue
    
    return False
    
    print(f"\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    analyze_schedule()
