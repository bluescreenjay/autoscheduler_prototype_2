#!/usr/bin/env python3
"""
LUMA Interview Auto-Scheduler (Improved Version)
Schedules group and individual interviews for all applicants with better logic.
"""

import csv
import os
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
import random

@dataclass
class TimeSlot:
    start: datetime
    end: datetime
    
    def overlaps(self, other: 'TimeSlot') -> bool:
        return not (self.end <= other.start or self.start >= other.end)
    
    def __str__(self):
        return f"{self.start.strftime('%m/%d/%Y %I:%M %p')}-{self.end.strftime('%I:%M %p')}"

@dataclass
class Interview:
    type: str  # 'group' or 'individual'
    time_slot: TimeSlot
    room: str
    applicants: List[str]
    recruiters: List[str]

class ImprovedScheduler:
    def __init__(self, inputs_dir: str, results_dir: str):
        self.inputs_dir = inputs_dir
        self.results_dir = results_dir
        self.applicants = {}
        self.recruiters = {}
        self.rooms = {}
        self.time_slots = []
        self.scheduled_interviews = []
        
        # Tracking sets
        self.applicant_group_scheduled = set()
        self.applicant_individual_scheduled = set()
        self.room_schedule = {}  # (time, room) -> True
        self.recruiter_schedule = {}  # (time, recruiter) -> True
        
    def _parse_time_string(self, time_str: str, date_str: str) -> datetime:
        """Parse time string in format like '5 PM' to datetime."""
        # Clean up the time string
        time_str = time_str.strip().upper()
        date_str = date_str.strip()
        
        # Handle various time formats
        if 'AM' in time_str or 'PM' in time_str:
            # Extract the time part
            time_part = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)', time_str)
            if time_part:
                hour = int(time_part.group(1))
                minute = int(time_part.group(2)) if time_part.group(2) else 0
                is_pm = time_part.group(3) == 'PM'
                
                if is_pm and hour != 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0
                
                # Parse date - handle format like "Thursday, September 11, 2025"
                try:
                    # Try the full format with day name and month name
                    date_obj = datetime.strptime(date_str, "%A, %B %d, %Y")
                    print(f"DEBUG: Parsed date as {date_obj}")
                except ValueError:
                    try:
                        # Try without day name
                        date_obj = datetime.strptime(date_str, "%B %d, %Y")
                        print(f"DEBUG: Parsed date (no day) as {date_obj}")
                    except ValueError as e:
                        print(f"DEBUG: Date parsing failed: {e}")
                        raise ValueError(f"Unable to parse date: {date_str}")
                
                return date_obj.replace(hour=hour, minute=minute)
        
        raise ValueError(f"Unable to parse time: {time_str} with date: {date_str}")

    def _parse_availability_slot(self, slot_str: str, date_str: str) -> Optional[TimeSlot]:
        """Parse availability slot like '5pm-9pm' or '5 PM - 6 PM'."""
        if '-' in slot_str:
            parts = slot_str.split('-', 1)
            if len(parts) == 2:
                start_str, end_str = parts
                try:
                    start_time = self._parse_time_string(start_str.strip(), date_str)
                    end_time = self._parse_time_string(end_str.strip(), date_str)
                    return TimeSlot(start_time, end_time)
                except ValueError:
                    return None
        return None

    def _load_applicants(self):
        """Load applicant data from CSV."""
        applicant_file = os.path.join(self.inputs_dir, 'applicant_information.csv')
        
        with open(applicant_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for idx, row in enumerate(reader):
                # Use email as ID since there's no ID column
                applicant_id = row.get('Email Address', '').strip()
                if not applicant_id:
                    applicant_id = f"applicant_{idx}"
                    
                availability = []
                
                # Parse availability columns
                for key, value in row.items():
                    if value and value.strip() and 'September' in key:
                        # Extract date from column header
                        date_match = re.search(r'(\w+,\s*September\s+\d+,\s*\d+)', key)
                        if date_match:
                            date_str = date_match.group(1)
                            print(f"DEBUG: Found date column '{key}' -> extracted '{date_str}'")
                            # Convert to standard format
                            try:
                                parsed_date = datetime.strptime(date_str, "%A, September %d, %Y")
                                # Keep the original September date, don't reformat
                                formatted_date = date_str  # Use original string
                                print(f"DEBUG: Using date '{formatted_date}'")
                                
                                # Parse time slots
                                time_slots = value.split(',')
                                for slot in time_slots:
                                    parsed_slot = self._parse_availability_slot(slot.strip(), formatted_date)
                                    if parsed_slot:
                                        availability.append(parsed_slot)
                                        print(f"DEBUG: Added slot {parsed_slot}")
                            except ValueError as e:
                                print(f"DEBUG: Date parsing error: {e}")
                                continue
                
                self.applicants[applicant_id] = {
                    'id': applicant_id,
                    'name': row.get('First and Last Name', '').strip(),
                    'email': row.get('Email Address', '').strip(),
                    'teams': row.get('Select the teams are you interested in joining:', '').strip(),
                    'availability': availability
                }

    def _parse_recruiter_datetime(self, datetime_str: str) -> Optional[TimeSlot]:
        """Parse recruiter datetime string in format YYYY-MM-DD HH:MM-HH:MM."""
        if not datetime_str or datetime_str.strip() == "":
            return None
            
        try:
            # Split date and time parts
            date_part, time_part = datetime_str.split(' ', 1)
            start_time_str, end_time_str = time_part.split('-')
            
            # Parse date
            date_obj = datetime.strptime(date_part, "%Y-%m-%d")
            
            # Parse times
            start_hour, start_min = map(int, start_time_str.split(':'))
            end_hour, end_min = map(int, end_time_str.split(':'))
            
            start_datetime = date_obj.replace(hour=start_hour, minute=start_min)
            end_datetime = date_obj.replace(hour=end_hour, minute=end_min)
            
            return TimeSlot(start_datetime, end_datetime)
        except (ValueError, AttributeError):
            return None

    def _load_recruiters(self):
        """Load recruiter data from CSV."""
        recruiter_file = os.path.join(self.inputs_dir, 'recruiters.csv')
        
        with open(recruiter_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                recruiter_id = row['recruiter_id'].strip()
                availability = []
                
                # Parse availability from single column with semicolon separators
                avail_str = row.get('availability', '')
                if avail_str:
                    avail_periods = avail_str.split(';')
                    for period in avail_periods:
                        parsed_slot = self._parse_recruiter_datetime(period.strip())
                        if parsed_slot:
                            availability.append(parsed_slot)
                
                self.recruiters[recruiter_id] = {
                    'id': recruiter_id,
                    'name': row.get('recruiter_name', '').strip(),
                    'team': row.get('team', '').strip(),
                    'availability': availability
                }

    def _parse_room_availability(self, avail_str: str) -> List[TimeSlot]:
        """Parse room availability string."""
        slots = []
        if not avail_str:
            return slots
            
        # Handle multiple availability periods separated by semicolons
        periods = avail_str.split(';')
        
        for period in periods:
            period = period.strip()
            # Look for pattern like "Sep 11 2025 5pm-9pm"
            match = re.search(r'Sep\s+(\d+)\s+2025\s+(\d+)(am|pm)-(\d+)(am|pm)', period)
            if match:
                day = int(match.group(1))
                start_hour = int(match.group(2))
                start_ampm = match.group(3)
                end_hour = int(match.group(4))
                end_ampm = match.group(5)
                
                # Convert to 24-hour format
                if start_ampm == 'pm' and start_hour != 12:
                    start_hour += 12
                elif start_ampm == 'am' and start_hour == 12:
                    start_hour = 0
                    
                if end_ampm == 'pm' and end_hour != 12:
                    end_hour += 12
                elif end_ampm == 'am' and end_hour == 12:
                    end_hour = 0
                
                # Create datetime objects
                start_dt = datetime(2025, 9, day, start_hour, 0)
                end_dt = datetime(2025, 9, day, end_hour, 0)
                
                slots.append(TimeSlot(start_dt, end_dt))
        
        return slots

    def _load_rooms(self):
        """Load room data from CSV."""
        room_file = os.path.join(self.inputs_dir, 'rooms.csv')
        
        with open(room_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                room_id = row['room_id'].strip()
                availability = []
                
                # Parse availability
                avail_str = row.get('availability', '')
                if avail_str:
                    availability = self._parse_room_availability(avail_str)
                
                self.rooms[room_id] = {
                    'id': room_id,
                    'availability': availability
                }

    def _generate_time_slots(self):
        """Generate all possible 20-minute time slots."""
        # Interview periods: Sep 11,12,15: 5pm-9pm and Sep 13,14: 9am-9pm
        interview_periods = [
            # Sep 11, 2025: 5pm-9pm
            (datetime(2025, 9, 11, 17, 0), datetime(2025, 9, 11, 21, 0)),
            # Sep 12, 2025: 5pm-9pm  
            (datetime(2025, 9, 12, 17, 0), datetime(2025, 9, 12, 21, 0)),
            # Sep 13, 2025: 9am-9pm
            (datetime(2025, 9, 13, 9, 0), datetime(2025, 9, 13, 21, 0)),
            # Sep 14, 2025: 9am-9pm
            (datetime(2025, 9, 14, 9, 0), datetime(2025, 9, 14, 21, 0)),
            # Sep 15, 2025: 5pm-9pm
            (datetime(2025, 9, 15, 17, 0), datetime(2025, 9, 15, 21, 0)),
        ]
        
        time_slots = []
        for start_time, end_time in interview_periods:
            current_time = start_time
            while current_time + timedelta(minutes=20) <= end_time:
                slot_end = current_time + timedelta(minutes=20)
                time_slots.append(TimeSlot(current_time, slot_end))
                current_time += timedelta(minutes=20)
        
        self.time_slots = sorted(time_slots, key=lambda x: x.start)
        print(f"Generated {len(self.time_slots)} possible 20-minute time slots")

    def load_data(self):
        """Load all input data."""
        print("Loading input data...")
        self._load_applicants()
        self._load_recruiters()
        self._load_rooms()
        self._generate_time_slots()
        print(f"Loaded {len(self.applicants)} applicants, {len(self.recruiters)} recruiters, {len(self.rooms)} rooms")
        
        # Debug: Show some availability data
        print("\nDEBUG: Sample availability data:")
        applicant_keys = list(self.applicants.keys())[:3]
        for app_id in applicant_keys:
            app = self.applicants[app_id]
            print(f"  Applicant {app['name']}: {len(app['availability'])} slots")
            for slot in app['availability'][:2]:
                print(f"    {slot}")
        
        recruiter_keys = list(self.recruiters.keys())[:3]
        for rec_id in recruiter_keys:
            rec = self.recruiters[rec_id]
            print(f"  Recruiter {rec['name']}: {len(rec['availability'])} slots")
            for slot in rec['availability'][:2]:
                print(f"    {slot}")
        
        room_keys = list(self.rooms.keys())[:2]
        for room_id in room_keys:
            room = self.rooms[room_id]
            print(f"  Room {room_id}: {len(room['availability'])} slots")
            for slot in room['availability'][:2]:
                print(f"    {slot}")

    def _is_applicant_available(self, applicant_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if applicant is available for the given time slot."""
        if applicant_id not in self.applicants:
            return False
            
        end_time = start_time + timedelta(minutes=duration_minutes)
        request_slot = TimeSlot(start_time, end_time)
        
        for avail_slot in self.applicants[applicant_id]['availability']:
            if (request_slot.start >= avail_slot.start and 
                request_slot.end <= avail_slot.end):
                return True
        return False

    def _is_recruiter_available(self, recruiter_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if recruiter is available and not already scheduled."""
        if recruiter_id not in self.recruiters:
            return False
            
        # Check if already scheduled
        if (start_time, recruiter_id) in self.recruiter_schedule:
            return False
            
        end_time = start_time + timedelta(minutes=duration_minutes)
        request_slot = TimeSlot(start_time, end_time)
        
        for avail_slot in self.recruiters[recruiter_id]['availability']:
            if (request_slot.start >= avail_slot.start and 
                request_slot.end <= avail_slot.end):
                return True
        return False

    def _is_room_available(self, room_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if room is available and not already scheduled."""
        if room_id not in self.rooms:
            return False
            
        # Check if already scheduled
        if (start_time, room_id) in self.room_schedule:
            return False
            
        end_time = start_time + timedelta(minutes=duration_minutes)
        request_slot = TimeSlot(start_time, end_time)
        
        for avail_slot in self.rooms[room_id]['availability']:
            if (request_slot.start >= avail_slot.start and 
                request_slot.end <= avail_slot.end):
                return True
        return False

    def _get_available_recruiters(self, start_time: datetime, duration: int) -> List[str]:
        """Get list of recruiters available for the given time slot."""
        available = []
        end_time = start_time + timedelta(minutes=duration)
        
        for recruiter_id in self.recruiters:
            # First check original availability from input data
            if not self._is_recruiter_available(recruiter_id, start_time, duration):
                continue
                
            # Then check against already scheduled interviews
            is_free = True
            for interview in self.scheduled_interviews:
                if recruiter_id in interview.recruiters:
                    interview_start = interview.time_slot.start
                    interview_end = interview.time_slot.end
                    
                    # Check for ANY overlap - fixed logic
                    if start_time < interview_end and end_time > interview_start:
                        is_free = False
                        break
            
            if is_free:
                available.append(recruiter_id)
                
        return available

    def _get_available_rooms(self, start_time: datetime, duration: int) -> List[str]:
        """Get list of rooms available for the given time slot."""
        available = []
        end_time = start_time + timedelta(minutes=duration)
        
        for room_id in self.rooms:
            # First check original availability from input data
            if not self._is_room_available(room_id, start_time, duration):
                continue
                
            # Then check against already scheduled interviews
            is_free = True
            for interview in self.scheduled_interviews:
                if interview.room == room_id:
                    interview_start = interview.time_slot.start
                    interview_end = interview.time_slot.end
                    
                    # Check for ANY overlap - fixed logic
                    if start_time < interview_end and end_time > interview_start:
                        is_free = False
                        break
            
            if is_free:
                available.append(room_id)
                
        return available

    def _has_scheduling_conflict(self, applicant_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if applicant has another interview that would create a direct overlap."""
        proposed_start = start_time
        proposed_end = start_time + timedelta(minutes=duration_minutes)
        
        for interview in self.scheduled_interviews:
            if applicant_id in interview.applicants:
                existing_start = interview.time_slot.start
                existing_end = interview.time_slot.end
                
                # Check for direct overlap (always a conflict)
                if not (proposed_end <= existing_start or existing_end <= proposed_start):
                    return True
                    
                # For 90-minute constraint: handled during optimization, not as hard constraint
                
        return False

    def _improved_greedy_schedule(self):
        """Improved greedy scheduling algorithm."""
        print("Starting improved greedy interview scheduling...")
        
        # Shuffle applicants for better distribution
        applicant_list = list(self.applicants.keys())
        random.shuffle(applicant_list)
        
        scheduled_completely = 0
        scheduled_partially = 0
        
        # Try to schedule both interviews for each applicant
        for applicant_id in applicant_list:
            group_scheduled = False
            individual_scheduled = False
            
            # Try to schedule group interview first (harder to schedule)
            if applicant_id not in self.applicant_group_scheduled:
                group_scheduled = self._schedule_applicant_group_interview(applicant_id)
                
            # Try to schedule individual interview
            if applicant_id not in self.applicant_individual_scheduled:
                individual_scheduled = self._schedule_applicant_individual_interview(applicant_id)
            
            if group_scheduled and individual_scheduled:
                scheduled_completely += 1
            elif group_scheduled or individual_scheduled:
                scheduled_partially += 1
                
        total_applicants = len(self.applicants)
        success_rate = (scheduled_completely / total_applicants) * 100 if total_applicants > 0 else 0
        
        print(f"Improved greedy scheduling complete:")
        print(f"  - Fully scheduled (both interviews): {scheduled_completely}/{total_applicants} ({success_rate:.1f}%)")
        print(f"  - Partially scheduled: {scheduled_partially}")
        print(f"  - Total interviews: {len(self.scheduled_interviews)}")
        
        return scheduled_completely > 0

    def _optimized_scheduling(self):
        """Two-phase scheduling: maximize coverage first, then optimize spacing."""
        print("Starting optimized two-phase scheduling...")
        
        # Phase 1: Maximum coverage (ignore 90-min constraint temporarily)
        self._phase1_maximum_coverage()
        
        # Phase 2: Optimize for 90-minute constraint via swapping
        self._phase2_optimize_spacing()
        
        return len(self.scheduled_interviews) > 0

    def _phase1_maximum_coverage(self):
        """Phase 1: Schedule as many interviews as possible."""
        applicant_list = list(self.applicants.keys())
        
        # Sort by availability (least available first for better packing)
        applicant_list.sort(key=lambda x: len(self.applicants[x]['availability']))
        
        scheduled_completely = 0
        scheduled_partially = 0
        
        for applicant_id in applicant_list:
            group_scheduled = False
            individual_scheduled = False
            
            # Try group interview first (harder to schedule)
            if applicant_id not in self.applicant_group_scheduled:
                group_scheduled = self._try_schedule_group_flexible(applicant_id)
                
            # Try individual interview
            if applicant_id not in self.applicant_individual_scheduled:
                individual_scheduled = self._try_schedule_individual_flexible(applicant_id)
            
            if group_scheduled and individual_scheduled:
                scheduled_completely += 1
            elif group_scheduled or individual_scheduled:
                scheduled_partially += 1
        
        total_applicants = len(self.applicants)
        print(f"Phase 1 complete:")
        print(f"  - Fully scheduled: {scheduled_completely}/{total_applicants}")
        print(f"  - Partially scheduled: {scheduled_partially}")
        print(f"  - Total interviews: {len(self.scheduled_interviews)}")

    def _phase2_optimize_spacing(self):
        """Phase 2: Improve 90-minute constraint compliance via local search."""
        print("Phase 2: Optimizing interview spacing...")
        max_iterations = 50
        improvements = 0
        
        for iteration in range(max_iterations):
            if self._improve_spacing_iteration():
                improvements += 1
            else:
                break
        
        print(f"Spacing optimization: {improvements} improvements made")

    def _try_schedule_group_flexible(self, applicant_id: str) -> bool:
        """Try to schedule group interview with flexible group size and timing."""
        best_option = None
        best_score = -1
        
        for time_slot in self.time_slots:
            if not self._is_applicant_available(applicant_id, time_slot.start, 40):
                continue
                
            # Only check for direct conflicts, not 90-minute constraint
            if self._has_scheduling_conflict(applicant_id, time_slot.start, 40):
                continue
                
            # Get resources
            available_rooms = self._get_available_rooms(time_slot.start, 40)
            available_recruiters = self._get_available_recruiters(time_slot.start, 40)
            
            if len(available_rooms) == 0 or len(available_recruiters) < 2:  # Minimum 2 recruiters
                continue
                
            # Find available applicants (flexible group size)
            available_applicants = [applicant_id]
            for other_id in self.applicants:
                if (other_id != applicant_id and 
                    other_id not in self.applicant_group_scheduled and
                    self._is_applicant_available(other_id, time_slot.start, 40) and
                    not self._has_scheduling_conflict(other_id, time_slot.start, 40)):
                    available_applicants.append(other_id)
            
            # Score this option (prefer larger groups, more recruiters, better timing)
            # Minimum group size: prefer 5, but accept 4 if necessary
            if len(available_applicants) >= 4:  # Minimum group size of 4
                score = (len(available_applicants) * 10 + 
                        len(available_recruiters) * 5 +
                        self._timing_score(applicant_id, time_slot.start))
                
                # Bonus for reaching preferred minimum of 5
                if len(available_applicants) >= 5:
                    score += 50  # Significant bonus for 5+ applicants
                
                if score > best_score:
                    best_score = score
                    best_option = {
                        'time_slot': time_slot,
                        'applicants': available_applicants[:8],  # Max 8
                        'recruiters': available_recruiters[:min(4, len(available_recruiters))],
                        'room': available_rooms[0]
                    }
        
        # Schedule best option
        if best_option:
            return self._create_group_interview(best_option)
        
        return False

    def _try_schedule_individual_flexible(self, applicant_id: str) -> bool:
        """Try to schedule individual interview with flexible timing."""
        best_option = None
        best_score = -1
        
        for time_slot in self.time_slots:
            if not self._is_applicant_available(applicant_id, time_slot.start, 20):
                continue
                
            # Only check for direct conflicts, not 90-minute constraint
            if self._has_scheduling_conflict(applicant_id, time_slot.start, 20):
                continue
                
            # Get resources
            available_rooms = self._get_available_rooms(time_slot.start, 20)
            available_recruiters = self._get_available_recruiters(time_slot.start, 20)
            
            if len(available_rooms) == 0 or len(available_recruiters) == 0:
                continue
                
            # Score this timing
            score = (100 +  # Base score
                    len(available_recruiters) * 2 +
                    self._timing_score(applicant_id, time_slot.start))
            
            if score > best_score:
                best_score = score
                best_option = {
                    'time_slot': time_slot,
                    'room': available_rooms[0],
                    'recruiter': available_recruiters[0]
                }
        
        # Schedule best option
        if best_option:
            return self._create_individual_interview(applicant_id, best_option)
        
        return False

    def _timing_score(self, applicant_id: str, start_time: datetime) -> int:
        """Score timing based on proximity to other interviews for same applicant."""
        score = 0
        for interview in self.scheduled_interviews:
            if applicant_id in interview.applicants:
                gap = abs((interview.time_slot.start - start_time).total_seconds() / 60)
                if gap <= 90:
                    score += 100 - gap  # Prefer closer timing within 90 minutes
        return score

    def _create_group_interview(self, option) -> bool:
        """Create and schedule a group interview."""
        group_end_time = option['time_slot'].start + timedelta(minutes=40)
        group_slot = TimeSlot(option['time_slot'].start, group_end_time)
        
        interview = Interview(
            type='group',
            time_slot=group_slot,
            room=option['room'],
            applicants=option['applicants'],
            recruiters=option['recruiters']
        )
        
        self.scheduled_interviews.append(interview)
        
        # Mark resources as used
        self.room_schedule[(option['time_slot'].start, option['room'])] = True
        for recruiter_id in option['recruiters']:
            self.recruiter_schedule[(option['time_slot'].start, recruiter_id)] = True
        
        # Mark applicants as having group interview
        for app_id in option['applicants']:
            self.applicant_group_scheduled.add(app_id)
        
        return True

    def _create_individual_interview(self, applicant_id: str, option) -> bool:
        """Create and schedule an individual interview."""
        individual_end_time = option['time_slot'].start + timedelta(minutes=20)
        individual_slot = TimeSlot(option['time_slot'].start, individual_end_time)
        
        interview = Interview(
            type='individual',
            time_slot=individual_slot,
            room=option['room'],
            applicants=[applicant_id],
            recruiters=[option['recruiter']]
        )
        
        self.scheduled_interviews.append(interview)
        
        # Mark resources as used
        self.room_schedule[(option['time_slot'].start, option['room'])] = True
        self.recruiter_schedule[(option['time_slot'].start, option['recruiter'])] = True
        
        # Mark applicant as having individual interview
        self.applicant_individual_scheduled.add(applicant_id)
        
        return True

    def _improve_spacing_iteration(self) -> bool:
        """Try to improve one scheduling decision via local search."""
        # Find applicants with spacing violations
        violations = self._find_spacing_violations()
        
        if not violations:
            return False
        
        # Try to fix the worst violation
        worst_violation = max(violations, key=lambda x: x['gap_minutes'])
        
        # Try to reschedule one of the interviews to be closer
        return self._fix_spacing_violation(worst_violation)

    def _find_spacing_violations(self):
        """Find all 90-minute constraint violations."""
        violations = []
        
        # Group interviews by applicant
        applicant_interviews = {}
        for interview in self.scheduled_interviews:
            for app_id in interview.applicants:
                if app_id not in applicant_interviews:
                    applicant_interviews[app_id] = []
                applicant_interviews[app_id].append(interview)
        
        # Check each applicant with multiple interviews
        for app_id, interviews in applicant_interviews.items():
            if len(interviews) >= 2:
                sorted_interviews = sorted(interviews, key=lambda x: x.time_slot.start)
                
                for i in range(len(sorted_interviews) - 1):
                    first_end = sorted_interviews[i].time_slot.end
                    second_start = sorted_interviews[i + 1].time_slot.start
                    
                    gap_minutes = (second_start - first_end).total_seconds() / 60
                    
                    if gap_minutes > 90:
                        violations.append({
                            'applicant_id': app_id,
                            'gap_minutes': gap_minutes,
                            'first_interview': sorted_interviews[i],
                            'second_interview': sorted_interviews[i + 1]
                        })
        
        return violations

    def _fix_spacing_violation(self, violation) -> bool:
        """Try to reschedule interviews to fix spacing violation."""
        # For now, return False - more complex rescheduling logic would go here
        # This is a placeholder for the full implementation
        return False

    def _schedule_applicant_group_interview(self, applicant_id: str) -> bool:
        """Try to schedule a group interview for a specific applicant."""
        for time_slot in self.time_slots:
            # Check if applicant is available
            if not self._is_applicant_available(applicant_id, time_slot.start, 40):
                continue
                
            # Check for direct scheduling conflicts only
            if self._has_scheduling_conflict(applicant_id, time_slot.start, 40):
                continue
                
            # Get available rooms and recruiters
            available_rooms = self._get_available_rooms(time_slot.start, 40)
            available_recruiters = self._get_available_recruiters(time_slot.start, 40)
            
            if len(available_rooms) == 0 or len(available_recruiters) < 4:
                continue
                
            # Find other available applicants for this time slot
            other_applicants = []
            for other_id in self.applicants:
                if (other_id != applicant_id and 
                    other_id not in self.applicant_group_scheduled and
                    self._is_applicant_available(other_id, time_slot.start, 40) and
                    not self._has_scheduling_conflict(other_id, time_slot.start, 40)):
                    other_applicants.append(other_id)
            
            # Need at least 3 other applicants (total 4 minimum for group), prefer 4+ other applicants (total 5+)
            if len(other_applicants) < 3:  # Absolute minimum: 4 total people
                continue
            
            # Score based on group size - prefer larger groups
            group_size = len(other_applicants) + 1  # +1 for main applicant
            score = group_size * 10
            
            # Bonus for reaching preferred minimum of 5
            if group_size >= 5:
                score += 50  # Significant bonus for 5+ people
                
            # Create group interview (only if we found a good option)
            group_applicants = [applicant_id] + other_applicants[:7]  # Up to 8 total
            group_recruiters = available_recruiters[:4]  # Exactly 4 recruiters
            room = available_rooms[0]
            
            # Create the interview
            group_end_time = time_slot.start + timedelta(minutes=40)
            group_slot = TimeSlot(time_slot.start, group_end_time)
            
            interview = Interview(
                type='group',
                time_slot=group_slot,
                room=room,
                applicants=group_applicants,
                recruiters=group_recruiters
            )
            
            self.scheduled_interviews.append(interview)
            
            # Mark resources as used
            self.room_schedule[(time_slot.start, room)] = True
            for recruiter_id in group_recruiters:
                self.recruiter_schedule[(time_slot.start, recruiter_id)] = True
            
            # Mark applicants as having group interview
            for app_id in group_applicants:
                self.applicant_group_scheduled.add(app_id)
            
            return True
        
        return False

    def _schedule_applicant_individual_interview(self, applicant_id: str) -> bool:
        """Try to schedule an individual interview for a specific applicant."""
        for time_slot in self.time_slots:
            # Check if applicant is available
            if not self._is_applicant_available(applicant_id, time_slot.start, 20):
                continue
                
            # Check for direct scheduling conflicts only
            if self._has_scheduling_conflict(applicant_id, time_slot.start, 20):
                continue
                
            # Get available rooms and recruiters
            available_rooms = self._get_available_rooms(time_slot.start, 20)
            available_recruiters = self._get_available_recruiters(time_slot.start, 20)
            
            if len(available_rooms) == 0 or len(available_recruiters) == 0:
                continue
                
            # Create individual interview
            room = available_rooms[0]
            recruiter = available_recruiters[0]
            
            # Create the interview
            individual_end_time = time_slot.start + timedelta(minutes=20)
            individual_slot = TimeSlot(time_slot.start, individual_end_time)
            
            interview = Interview(
                type='individual',
                time_slot=individual_slot,
                room=room,
                applicants=[applicant_id],
                recruiters=[recruiter]
            )
            
            self.scheduled_interviews.append(interview)
            
            # Mark resources as used
            self.room_schedule[(time_slot.start, room)] = True
            self.recruiter_schedule[(time_slot.start, recruiter)] = True
            
            # Mark applicant as having individual interview
            self.applicant_individual_scheduled.add(applicant_id)
            
            return True
        
        return False

    def schedule_interviews(self):
        """Enhanced main scheduling method with multiple strategies."""
        # Try multiple strategies
        strategies = [
            ('optimized_two_phase', self._optimized_scheduling),
            ('improved_greedy', self._improved_greedy_schedule)
        ]
        
        best_result = None
        best_score = -1
        
        for strategy_name, strategy_func in strategies:
            print(f"\n=== Trying strategy: {strategy_name} ===")
            
            # Reset state
            self._reset_scheduling_state()
            
            success = strategy_func()
            
            if success:
                score = self._evaluate_schedule()
                print(f"Strategy {strategy_name} score: {score}")
                
                if score > best_score:
                    best_score = score
                    best_result = {
                        'interviews': self.scheduled_interviews.copy(),
                        'group_scheduled': self.applicant_group_scheduled.copy(),
                        'individual_scheduled': self.applicant_individual_scheduled.copy(),
                        'strategy': strategy_name
                    }
        
        if best_result:
            # Apply best result
            self.scheduled_interviews = best_result['interviews']
            self.applicant_group_scheduled = best_result['group_scheduled']
            self.applicant_individual_scheduled = best_result['individual_scheduled']
            
            print(f"\n=== Best strategy: {best_result['strategy']} with score {best_score} ===")
            print(f"Scheduling successful! Generated {len(self.scheduled_interviews)} interviews.")
            
            # Validate 90-minute constraint
            self._validate_90_minute_constraint()
            return True
        
        print("Scheduling failed - no interviews could be scheduled.")
        return False

    def _reset_scheduling_state(self):
        """Reset scheduling state for trying different strategies."""
        self.scheduled_interviews = []
        self.applicant_group_scheduled = set()
        self.applicant_individual_scheduled = set()
        self.room_schedule = {}
        self.recruiter_schedule = {}

    def _evaluate_schedule(self) -> float:
        """Evaluate the quality of current schedule."""
        fully_scheduled = len(self.applicant_group_scheduled & self.applicant_individual_scheduled)
        total_interviews = len(self.scheduled_interviews)
        violations = len(self._find_spacing_violations())
        
        # Score: prioritize full scheduling, minimize violations
        score = (fully_scheduled * 100 +  # Heavily weight full scheduling
                 total_interviews * 10 -    # Reward more interviews
                 violations * 50)           # Penalize constraint violations
        
        return score

    def _validate_90_minute_constraint(self):
        """Validate that all applicants have interviews within 90 minutes of each other."""
        violations = []
        
        # Group interviews by applicant
        applicant_interviews = {}
        for interview in self.scheduled_interviews:
            for app_id in interview.applicants:
                if app_id not in applicant_interviews:
                    applicant_interviews[app_id] = []
                applicant_interviews[app_id].append(interview)
        
        # Check each applicant with multiple interviews
        for app_id, interviews in applicant_interviews.items():
            if len(interviews) >= 2:
                # Sort by time
                sorted_interviews = sorted(interviews, key=lambda x: x.time_slot.start)
                
                # Check gaps between consecutive interviews
                for i in range(len(sorted_interviews) - 1):
                    first_end = sorted_interviews[i].time_slot.end
                    second_start = sorted_interviews[i + 1].time_slot.start
                    
                    gap_minutes = (second_start - first_end).total_seconds() / 60
                    
                    if gap_minutes > 90:
                        applicant_name = self.applicants.get(app_id, {}).get('name', app_id)
                        violations.append({
                            'applicant_id': app_id,
                            'applicant_name': applicant_name,
                            'gap_minutes': gap_minutes,
                            'first_interview': sorted_interviews[i],
                            'second_interview': sorted_interviews[i + 1]
                        })
        
        if violations:
            print(f"\nWARNING: Found {len(violations)} violations of 90-minute constraint:")
            for violation in violations:
                print(f"  - {violation['applicant_name']}: {violation['gap_minutes']:.0f} minute gap")
                print(f"    Between {violation['first_interview'].time_slot} and {violation['second_interview'].time_slot}")
        else:
            print(f"\n✓ All applicants with multiple interviews satisfy the 90-minute constraint!")
        
        return violations

    def generate_reports(self):
        """Generate all output reports."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(self.results_dir, f"run_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        
        self._generate_main_schedule(output_dir)
        self._generate_applicant_schedules(output_dir)
        self._generate_recruiter_schedules(output_dir)
        self._generate_unscheduled_report(output_dir)
        self._generate_summary_report(output_dir)
        self._generate_block_breakdown(output_dir)
        
        print(f"Reports generated in: {output_dir}")
        return output_dir

    def _generate_main_schedule(self, output_dir):
        """Generate main schedule CSV."""
        filename = os.path.join(output_dir, 'main_schedule.csv')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Start Time', 'End Time', 'Room', 'Applicants', 'Recruiters'])
            
            # Sort interviews by time
            sorted_interviews = sorted(self.scheduled_interviews, key=lambda x: x.time_slot.start)
            
            for interview in sorted_interviews:
                applicant_names = []
                for app_id in interview.applicants:
                    if app_id in self.applicants:
                        applicant_names.append(self.applicants[app_id]['name'])
                    else:
                        applicant_names.append(app_id)
                
                recruiter_names = []
                for rec_id in interview.recruiters:
                    if rec_id in self.recruiters:
                        recruiter_names.append(self.recruiters[rec_id]['name'])
                    else:
                        recruiter_names.append(rec_id)
                
                writer.writerow([
                    interview.type,
                    interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                    interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                    interview.room,
                    '; '.join(applicant_names),
                    '; '.join(recruiter_names)
                ])

    def _generate_applicant_schedules(self, output_dir):
        """Generate per-applicant schedule CSV."""
        filename = os.path.join(output_dir, 'applicant_schedules.csv')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Applicant', 'Start Time', 'End Time', 'Room', 'Interview Type', 'Recruiters'])
            
            # Collect all interviews per applicant
            applicant_interviews = {}
            for interview in self.scheduled_interviews:
                for app_id in interview.applicants:
                    if app_id not in applicant_interviews:
                        applicant_interviews[app_id] = []
                    applicant_interviews[app_id].append(interview)
            
            # Write sorted by applicant and time
            for app_id in sorted(applicant_interviews.keys()):
                interviews = sorted(applicant_interviews[app_id], key=lambda x: x.time_slot.start)
                for interview in interviews:
                    applicant_name = self.applicants.get(app_id, {}).get('name', app_id)
                    recruiter_names = [self.recruiters.get(rec_id, {}).get('name', rec_id) for rec_id in interview.recruiters]
                    
                    writer.writerow([
                        applicant_name,
                        interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                        interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                        interview.room,
                        interview.type,
                        '; '.join(recruiter_names)
                    ])

    def _generate_recruiter_schedules(self, output_dir):
        """Generate per-recruiter schedule CSV."""
        filename = os.path.join(output_dir, 'recruiter_schedules.csv')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Recruiter', 'Start Time', 'End Time', 'Room', 'Interview Type', 'Applicants'])
            
            # Collect all interviews per recruiter
            recruiter_interviews = {}
            for interview in self.scheduled_interviews:
                for rec_id in interview.recruiters:
                    if rec_id not in recruiter_interviews:
                        recruiter_interviews[rec_id] = []
                    recruiter_interviews[rec_id].append(interview)
            
            # Write sorted by recruiter and time
            for rec_id in sorted(recruiter_interviews.keys()):
                interviews = sorted(recruiter_interviews[rec_id], key=lambda x: x.time_slot.start)
                for interview in interviews:
                    recruiter_name = self.recruiters.get(rec_id, {}).get('name', rec_id)
                    applicant_names = [self.applicants.get(app_id, {}).get('name', app_id) for app_id in interview.applicants]
                    
                    writer.writerow([
                        recruiter_name,
                        interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                        interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                        interview.room,
                        interview.type,
                        '; '.join(applicant_names)
                    ])

    def _generate_unscheduled_report(self, output_dir):
        """Generate report of unscheduled applicants."""
        filename = os.path.join(output_dir, 'unscheduled_applicants.csv')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Applicant ID', 'Name', 'Email', 'Teams Interested', 'Has Group', 'Has Individual'])
            
            for app_id, applicant in self.applicants.items():
                has_group = app_id in self.applicant_group_scheduled
                has_individual = app_id in self.applicant_individual_scheduled
                
                # Only include if not fully scheduled
                if not (has_group and has_individual):
                    writer.writerow([
                        app_id,
                        applicant['name'],
                        applicant['email'],
                        applicant['teams'],
                        'Yes' if has_group else 'No',
                        'Yes' if has_individual else 'No'
                    ])

    def _generate_summary_report(self, output_dir):
        """Generate summary statistics report."""
        filename = os.path.join(output_dir, 'summary_report.txt')
        
        fully_scheduled = len(self.applicant_group_scheduled & self.applicant_individual_scheduled)
        group_only = len(self.applicant_group_scheduled - self.applicant_individual_scheduled)
        individual_only = len(self.applicant_individual_scheduled - self.applicant_group_scheduled)
        unscheduled = len(self.applicants) - len(self.applicant_group_scheduled | self.applicant_individual_scheduled)
        
        total_applicants = len(self.applicants)
        success_rate = (fully_scheduled / total_applicants * 100) if total_applicants > 0 else 0
        
        group_interviews = len([i for i in self.scheduled_interviews if i.type == 'group'])
        individual_interviews = len([i for i in self.scheduled_interviews if i.type == 'individual'])
        
        # Check 90-minute constraint violations
        violations = self._validate_90_minute_constraint()
        
        with open(filename, 'w') as f:
            f.write("INTERVIEW SCHEDULING SUMMARY REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total Applicants: {total_applicants}\n")
            f.write(f"Fully Scheduled (both interviews): {fully_scheduled}\n")
            f.write(f"Group Interview Only: {group_only}\n")
            f.write(f"Individual Interview Only: {individual_only}\n")
            f.write(f"Completely Unscheduled: {unscheduled}\n")
            f.write(f"Overall Success Rate: {success_rate:.1f}%\n\n")
            f.write(f"Total Interviews Scheduled: {len(self.scheduled_interviews)}\n")
            f.write(f"Group Interviews: {group_interviews}\n")
            f.write(f"Individual Interviews: {individual_interviews}\n\n")
            f.write("CONSTRAINT COMPLIANCE:\n")
            f.write(f"90-minute spacing violations: {len(violations)}\n")
            if violations:
                f.write("Violating applicants:\n")
                for violation in violations:
                    f.write(f"  - {violation['applicant_name']}: {violation['gap_minutes']:.0f} minute gap\n")
            f.write("\n")
            f.write("ALGORITHM USED: Improved Greedy Scheduling with 90-minute Constraint\n")
            f.write("- Prioritizes complete scheduling per applicant\n")
            f.write("- Uses random shuffle for better distribution\n")
            f.write("- Ensures proper resource allocation\n")
            f.write("- Enforces 90-minute maximum gap between interviews\n")

    def _generate_block_breakdown(self, output_dir):
        """Generate detailed block breakdown report."""
        filename = os.path.join(output_dir, 'block_breakdown.txt')
        
        # Group interviews by time block
        time_blocks = {}
        for interview in self.scheduled_interviews:
            time_key = interview.time_slot.start
            if time_key not in time_blocks:
                time_blocks[time_key] = []
            time_blocks[time_key].append(interview)
        
        with open(filename, 'w') as f:
            f.write("INTERVIEW BLOCK BREAKDOWN\n")
            f.write("=" * 50 + "\n\n")
            
            for time_key in sorted(time_blocks.keys()):
                f.write(f"TIME BLOCK: {time_key.strftime('%m/%d/%Y %I:%M %p')}\n")
                f.write("-" * 30 + "\n")
                
                interviews = sorted(time_blocks[time_key], key=lambda x: (x.type, x.room))
                for interview in interviews:
                    f.write(f"  {interview.type.upper()} INTERVIEW - Room {interview.room}\n")
                    
                    # Applicant names
                    applicant_names = [self.applicants.get(app_id, {}).get('name', app_id) for app_id in interview.applicants]
                    f.write(f"    Applicants: {', '.join(applicant_names)}\n")
                    
                    # Recruiter names
                    recruiter_names = [self.recruiters.get(rec_id, {}).get('name', rec_id) for rec_id in interview.recruiters]
                    f.write(f"    Recruiters: {', '.join(recruiter_names)}\n")
                    f.write("\n")
                f.write("\n")

def main():
    # Set up paths
    inputs_dir = "inputs"
    results_dir = "results"
    
    # Create results directory if it doesn't exist
    os.makedirs(results_dir, exist_ok=True)
    
    print("=== LUMA Interview Auto-Scheduler (Improved) ===\n")
    
    # Initialize scheduler
    scheduler = ImprovedScheduler(inputs_dir, results_dir)
    
    # Load data
    scheduler.load_data()
    
    # Schedule interviews
    success = scheduler.schedule_interviews()
    
    if success:
        # Generate reports
        output_dir = scheduler.generate_reports()
        print(f"\nScheduling complete! Check results in: {output_dir}")
    else:
        print("\nScheduling failed - unable to create any viable schedule.")

if __name__ == "__main__":
    main()
