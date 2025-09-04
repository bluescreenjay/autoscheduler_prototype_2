#!/usr/bin/env python3
"""
Simplified auto-scheduling system that focuses on core constraints first.
"""

import csv
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import json
import random

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError as e:
    HAS_ORTOOLS = False
    print(f"WARNING: OR-Tools import failed: {e}")


@dataclass
class TimeSlot:
    """Represents a time slot with start and end times."""
    start: datetime
    end: datetime
    
    def __str__(self):
        return f"{self.start.strftime('%m/%d %I:%M %p')}-{self.end.strftime('%I:%M %p')}"
    
    def overlaps(self, other: 'TimeSlot') -> bool:
        """Check if this time slot overlaps with another."""
        return self.start < other.end and other.start < self.end


@dataclass 
class Applicant:
    """Represents an applicant with their information and availability."""
    id: str
    name: str
    email: str
    teams: List[str]
    availability: List[TimeSlot]


@dataclass
class Recruiter:
    """Represents a recruiter with their information and availability."""
    id: str
    name: str
    team: str
    availability: List[TimeSlot]


@dataclass
class Room:
    """Represents a room with its availability."""
    id: str
    availability: List[TimeSlot]


@dataclass
class Interview:
    """Represents a scheduled interview."""
    type: str  # 'group' or 'individual'
    time_slot: TimeSlot
    room: str
    applicants: List[str]
    recruiters: List[str]


class SimpleScheduler:
    """Simplified scheduler with greedy algorithm fallback."""
    
    def __init__(self, inputs_dir: str, results_dir: str):
        self.inputs_dir = inputs_dir
        self.results_dir = results_dir
        self.applicants: Dict[str, Applicant] = {}
        self.recruiters: Dict[str, Recruiter] = {}
        self.rooms: Dict[str, Room] = {}
        self.time_slots: List[TimeSlot] = []
        self.scheduled_interviews: List[Interview] = []
        self.unscheduled_applicants: List[str] = []
        
        # Tracking what's scheduled
        self.room_schedule: Dict[Tuple[datetime, str], bool] = {}  # (time, room) -> occupied
        self.recruiter_schedule: Dict[Tuple[datetime, str], bool] = {}  # (time, recruiter) -> occupied
        self.applicant_group_scheduled: Set[str] = set()
        self.applicant_individual_scheduled: Set[str] = set()
        
        # Create results directory
        os.makedirs(results_dir, exist_ok=True)
        
    def load_data(self):
        """Load all input data from CSV files."""
        print("Loading input data...")
        self._load_applicants()
        self._load_recruiters()
        self._load_rooms()
        self._generate_time_slots()
        print(f"Loaded {len(self.applicants)} applicants, {len(self.recruiters)} recruiters, {len(self.rooms)} rooms")
        
    def _parse_time_string(self, time_str: str, date_str: str) -> datetime:
        """Parse time string like '5 PM - 6 PM' with a given date."""
        start_match = re.search(r'(\d+)\s*(AM|PM)', time_str)
        if start_match:
            hour = int(start_match.group(1))
            period = start_match.group(2)
            
            if period == 'PM' and hour != 12:
                hour += 12
            elif period == 'AM' and hour == 12:
                hour = 0
                
            date_match = re.search(r'September (\d+), 2025', date_str)
            if date_match:
                day = int(date_match.group(1))
                return datetime(2025, 9, day, hour, 0)
        
        return None
        
    def _parse_availability_slot(self, slot_str: str, date_str: str) -> Optional[TimeSlot]:
        """Parse availability slot like '5 PM - 6 PM' for a given date."""
        parts = slot_str.strip().split(' - ')
        if len(parts) != 2:
            return None
            
        start_str, end_str = parts
        start_time = self._parse_time_string(start_str, date_str)
        end_time = self._parse_time_string(end_str, date_str)
        
        if start_time and end_time:
            return TimeSlot(start_time, end_time)
        return None
        
    def _load_applicants(self):
        """Load applicant data from CSV."""
        filepath = os.path.join(self.inputs_dir, 'applicant_information.csv')
        
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                applicant_id = row['Email Address'].split('@')[0]
                name = row['First and Last Name']
                email = row['Email Address']
                
                # Parse teams
                teams_str = row['Select the teams are you interested in joining:']
                teams = []
                if 'Astra' in teams_str:
                    teams.append('Astra')
                if 'Juvo' in teams_str:
                    teams.append('Juvo')
                if 'Infinitum' in teams_str:
                    teams.append('Infinitum')
                if 'Terra' in teams_str:
                    teams.append('Terra')
                
                # Parse availability
                availability = []
                date_columns = [
                    'Thursday, September 11, 2025',
                    'Friday, September 12, 2025', 
                    'Saturday, September 13, 2025',
                    'Sunday, September 14, 2025',
                    'Monday, September 15, 2025'
                ]
                
                for date_col in date_columns:
                    if date_col in row and row[date_col]:
                        slots_str = row[date_col]
                        for slot_str in slots_str.split(','):
                            slot = self._parse_availability_slot(slot_str.strip(), date_col)
                            if slot:
                                availability.append(slot)
                
                self.applicants[applicant_id] = Applicant(
                    id=applicant_id,
                    name=name,
                    email=email,
                    teams=teams,
                    availability=availability
                )
                
    def _parse_recruiter_datetime(self, datetime_str: str) -> Optional[TimeSlot]:
        """Parse recruiter datetime string like '2025-09-11 17:00-21:00'."""
        try:
            date_part, time_part = datetime_str.split(' ')
            start_time_str, end_time_str = time_part.split('-')
            
            year, month, day = map(int, date_part.split('-'))
            start_hour, start_min = map(int, start_time_str.split(':'))
            start_dt = datetime(year, month, day, start_hour, start_min)
            
            end_hour, end_min = map(int, end_time_str.split(':'))
            end_dt = datetime(year, month, day, end_hour, end_min)
            
            return TimeSlot(start_dt, end_dt)
        except:
            return None
            
    def _load_recruiters(self):
        """Load recruiter data from CSV."""
        filepath = os.path.join(self.inputs_dir, 'recruiters.csv')
        
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                recruiter_id = row['recruiter_id']
                name = row['recruiter_name']
                team = row['team']
                
                availability = []
                if row['availability']:
                    for slot_str in row['availability'].split(';'):
                        slot = self._parse_recruiter_datetime(slot_str.strip())
                        if slot:
                            availability.append(slot)
                
                self.recruiters[recruiter_id] = Recruiter(
                    id=recruiter_id,
                    name=name,
                    team=team,
                    availability=availability
                )
                
    def _parse_room_availability(self, avail_str: str) -> List[TimeSlot]:
        """Parse room availability string."""
        availability = []
        
        for date_range in avail_str.split(';'):
            date_range = date_range.strip()
            
            match = re.match(r'Sep (\d+) 2025 (\d+)(am|pm)-(\d+)(am|pm)', date_range)
            if match:
                day = int(match.group(1))
                start_hour = int(match.group(2))
                start_period = match.group(3)
                end_hour = int(match.group(4))
                end_period = match.group(5)
                
                if start_period == 'pm' and start_hour != 12:
                    start_hour += 12
                elif start_period == 'am' and start_hour == 12:
                    start_hour = 0
                    
                if end_period == 'pm' and end_hour != 12:
                    end_hour += 12
                elif end_period == 'am' and end_hour == 12:
                    end_hour = 0
                
                start_dt = datetime(2025, 9, day, start_hour, 0)
                end_dt = datetime(2025, 9, day, end_hour, 0)
                
                availability.append(TimeSlot(start_dt, end_dt))
                
        return availability
        
    def _load_rooms(self):
        """Load room data from CSV."""
        filepath = os.path.join(self.inputs_dir, 'rooms.csv')
        
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                room_id = row['room_id']
                availability = self._parse_room_availability(row['availability'])
                
                self.rooms[room_id] = Room(
                    id=room_id,
                    availability=availability
                )
                
    def _generate_time_slots(self):
        """Generate all possible 20-minute time slots."""
        dates_and_hours = [
            (datetime(2025, 9, 11), 17, 21),  # Sep 11: 5pm-9pm
            (datetime(2025, 9, 12), 17, 21),  # Sep 12: 5pm-9pm
            (datetime(2025, 9, 13), 9, 21),   # Sep 13: 9am-9pm
            (datetime(2025, 9, 14), 9, 21),   # Sep 14: 9am-9pm
            (datetime(2025, 9, 15), 17, 21),  # Sep 15: 5pm-9pm
        ]
        
        for date, start_hour, end_hour in dates_and_hours:
            current_time = date.replace(hour=start_hour, minute=0)
            end_time = date.replace(hour=end_hour, minute=0)
            
            while current_time < end_time:
                slot_end = current_time + timedelta(minutes=20)
                if slot_end <= end_time:
                    self.time_slots.append(TimeSlot(current_time, slot_end))
                current_time += timedelta(minutes=20)
                
        print(f"Generated {len(self.time_slots)} possible 20-minute time slots")
        
    def schedule_interviews(self):
        """Main scheduling function using greedy algorithm."""
        print("Starting greedy interview scheduling...")
        
        # First try OR-Tools if available
        if HAS_ORTOOLS:
            success = self._try_ortools_scheduling()
            if success:
                return True
        
        # Fallback to greedy algorithm
        print("Using greedy scheduling algorithm...")
        return self._greedy_schedule()
        
    def _try_ortools_scheduling(self):
        """Try scheduling with OR-Tools but with relaxed constraints."""
        print("Attempting OR-Tools scheduling with relaxed constraints...")
        
        model = cp_model.CpModel()
        
        # Simplified model - just focus on basic constraints
        applicant_list = list(self.applicants.keys())[:50]  # Start with fewer applicants
        
        # Variables for group interviews
        group_vars = {}
        individual_vars = {}
        
        for applicant_id in applicant_list:
            group_vars[applicant_id] = {}
            individual_vars[applicant_id] = {}
            
            for i, time_slot in enumerate(self.time_slots):
                group_vars[applicant_id][i] = {}
                individual_vars[applicant_id][i] = {}
                
                for room_id in list(self.rooms.keys())[:10]:  # Use fewer rooms
                    group_vars[applicant_id][i][room_id] = model.NewBoolVar(
                        f'group_{applicant_id}_{i}_{room_id}'
                    )
                    individual_vars[applicant_id][i][room_id] = model.NewBoolVar(
                        f'individual_{applicant_id}_{i}_{room_id}'
                    )
        
        # Basic constraints
        for applicant_id in applicant_list:
            # Each applicant gets exactly one of each type
            model.Add(
                sum(group_vars[applicant_id][i][room_id] 
                    for i in range(len(self.time_slots))
                    for room_id in list(self.rooms.keys())[:10]) == 1
            )
            
            model.Add(
                sum(individual_vars[applicant_id][i][room_id]
                    for i in range(len(self.time_slots))
                    for room_id in list(self.rooms.keys())[:10]) == 1
            )
        
        # Room capacity constraints
        for i in range(len(self.time_slots)):
            for room_id in list(self.rooms.keys())[:10]:
                model.Add(
                    sum(group_vars[applicant_id][i][room_id] 
                        for applicant_id in applicant_list) +
                    sum(individual_vars[applicant_id][i][room_id]
                        for applicant_id in applicant_list) <= 1
                )
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("OR-Tools found a solution for subset!")
            # Extract and apply solution
            self._extract_simple_solution(solver, group_vars, individual_vars, applicant_list)
            return True
        else:
            print("OR-Tools could not find solution, falling back to greedy algorithm")
            return False
            
    def _extract_simple_solution(self, solver, group_vars, individual_vars, applicant_list):
        """Extract solution from simplified OR-Tools model."""
        for applicant_id in applicant_list:
            # Find group interview
            for i, time_slot in enumerate(self.time_slots):
                for room_id in list(self.rooms.keys())[:10]:
                    if solver.Value(group_vars[applicant_id][i][room_id]):
                        # Create a group interview (simplified - just this applicant for now)
                        group_end_time = time_slot.start + timedelta(minutes=40)
                        group_slot = TimeSlot(time_slot.start, group_end_time)
                        
                        # Find available recruiters
                        available_recruiters = self._get_available_recruiters(time_slot.start, duration=40)[:4]
                        
                        interview = Interview(
                            type='group',
                            time_slot=group_slot,
                            room=room_id,
                            applicants=[applicant_id],
                            recruiters=available_recruiters
                        )
                        
                        self.scheduled_interviews.append(interview)
                        self.applicant_group_scheduled.add(applicant_id)
                        
                        # Mark resources as used
                        self.room_schedule[(time_slot.start, room_id)] = True
                        for recruiter_id in available_recruiters:
                            self.recruiter_schedule[(time_slot.start, recruiter_id)] = True
                        
                        break
            
            # Find individual interview
            for i, time_slot in enumerate(self.time_slots):
                for room_id in list(self.rooms.keys())[:10]:
                    if solver.Value(individual_vars[applicant_id][i][room_id]):
                        # Find available recruiter
                        available_recruiters = self._get_available_recruiters(time_slot.start, duration=20)[:1]
                        
                        if available_recruiters:
                            interview = Interview(
                                type='individual',
                                time_slot=time_slot,
                                room=room_id,
                                applicants=[applicant_id],
                                recruiters=available_recruiters
                            )
                            
                            self.scheduled_interviews.append(interview)
                            self.applicant_individual_scheduled.add(applicant_id)
                            
                            # Mark resources as used
                            self.room_schedule[(time_slot.start, room_id)] = True
                            self.recruiter_schedule[(time_slot.start, available_recruiters[0])] = True
                        
                        break
                        
    def _greedy_schedule(self):
        """Greedy scheduling algorithm."""
        print("Starting greedy scheduling...")
        
        # Sort applicants by availability (least available first)
        applicant_list = list(self.applicants.keys())
        applicant_list.sort(key=lambda x: len(self.applicants[x].availability))
        
        scheduled_count = 0
        
        # Schedule group interviews first
        print("Scheduling group interviews...")
        groups_scheduled = self._schedule_group_interviews_greedy()
        print(f"Scheduled {groups_scheduled} group interviews")
        
        # Schedule individual interviews
        print("Scheduling individual interviews...")
        individual_scheduled = self._schedule_individual_interviews_greedy()
        print(f"Scheduled {individual_scheduled} individual interviews")
        
        # Determine unscheduled applicants
        self.unscheduled_applicants = []
        for applicant_id in self.applicants:
            if (applicant_id not in self.applicant_group_scheduled or 
                applicant_id not in self.applicant_individual_scheduled):
                self.unscheduled_applicants.append(applicant_id)
        
        scheduled_count = len(self.applicants) - len(self.unscheduled_applicants)
        success_rate = (scheduled_count / len(self.applicants)) * 100
        
        print(f"Greedy scheduling complete: {scheduled_count}/{len(self.applicants)} applicants scheduled ({success_rate:.1f}%)")
        
        return scheduled_count > 0
        
    def _schedule_group_interviews_greedy(self):
        """Schedule group interviews using greedy approach."""
        groups_scheduled = 0
        remaining_applicants = set(self.applicants.keys())
        
        for time_slot in self.time_slots:
            for room_id in self.rooms:
                # Check if room and time are available
                if (time_slot.start, room_id) in self.room_schedule:
                    continue
                    
                # Check if room is available during this time
                if not self._is_room_available(room_id, time_slot.start, 40):
                    continue
                
                # Find available recruiters
                available_recruiters = self._get_available_recruiters(time_slot.start, duration=40)
                if len(available_recruiters) < 4:
                    continue
                
                # Find available applicants for this time
                available_applicants = []
                for applicant_id in remaining_applicants:
                    if (applicant_id not in self.applicant_group_scheduled and 
                        self._is_applicant_available(applicant_id, time_slot.start, 40)):
                        available_applicants.append(applicant_id)
                
                # Need at least 4 applicants for a group
                if len(available_applicants) < 4:
                    continue
                
                # Create group interview with up to 8 applicants
                group_applicants = available_applicants[:8]
                group_recruiters = available_recruiters[:4]
                
                # Create the interview
                group_end_time = time_slot.start + timedelta(minutes=40)
                group_slot = TimeSlot(time_slot.start, group_end_time)
                
                interview = Interview(
                    type='group',
                    time_slot=group_slot,
                    room=room_id,
                    applicants=group_applicants,
                    recruiters=group_recruiters
                )
                
                self.scheduled_interviews.append(interview)
                groups_scheduled += 1
                
                # Mark resources as used
                self.room_schedule[(time_slot.start, room_id)] = True
                for recruiter_id in group_recruiters:
                    self.recruiter_schedule[(time_slot.start, recruiter_id)] = True
                
                # Mark applicants as having group interview
                for applicant_id in group_applicants:
                    self.applicant_group_scheduled.add(applicant_id)
                    remaining_applicants.discard(applicant_id)
                
                if len(remaining_applicants) == 0:
                    break
            
            if len(remaining_applicants) == 0:
                break
                
        return groups_scheduled
        
    def _schedule_individual_interviews_greedy(self):
        """Schedule individual interviews using greedy approach."""
        individual_scheduled = 0
        
        # Go through all applicants who need individual interviews
        for applicant_id in self.applicants:
            if applicant_id in self.applicant_individual_scheduled:
                continue
                
            # Find a suitable time slot
            for time_slot in self.time_slots:
                # Check if applicant is available
                if not self._is_applicant_available(applicant_id, time_slot.start, 20):
                    continue
                
                # Find available room
                available_room = None
                for room_id in self.rooms:
                    if ((time_slot.start, room_id) not in self.room_schedule and
                        self._is_room_available(room_id, time_slot.start, 20)):
                        available_room = room_id
                        break
                
                if not available_room:
                    continue
                
                # Find suitable recruiter
                applicant = self.applicants[applicant_id]
                suitable_recruiter = None
                
                # First try to find recruiter from applicant's interested teams
                for recruiter_id, recruiter in self.recruiters.items():
                    if ((time_slot.start, recruiter_id) not in self.recruiter_schedule and
                        self._is_recruiter_available(recruiter_id, time_slot.start, 20) and
                        (recruiter.team in applicant.teams or recruiter.team == 'All')):
                        suitable_recruiter = recruiter_id
                        break
                
                # If no team match, find any available recruiter
                if not suitable_recruiter:
                    for recruiter_id in self.recruiters:
                        if ((time_slot.start, recruiter_id) not in self.recruiter_schedule and
                            self._is_recruiter_available(recruiter_id, time_slot.start, 20)):
                            suitable_recruiter = recruiter_id
                            break
                
                if not suitable_recruiter:
                    continue
                
                # Create individual interview
                interview = Interview(
                    type='individual',
                    time_slot=time_slot,
                    room=available_room,
                    applicants=[applicant_id],
                    recruiters=[suitable_recruiter]
                )
                
                self.scheduled_interviews.append(interview)
                individual_scheduled += 1
                
                # Mark resources as used
                self.room_schedule[(time_slot.start, available_room)] = True
                self.recruiter_schedule[(time_slot.start, suitable_recruiter)] = True
                self.applicant_individual_scheduled.add(applicant_id)
                
                break
                
        return individual_scheduled
        
    def _is_applicant_available(self, applicant_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if applicant is available for the given time period."""
        applicant = self.applicants[applicant_id]
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        for availability_slot in applicant.availability:
            if (availability_slot.start <= start_time and 
                end_time <= availability_slot.end):
                return True
        return False
        
    def _is_recruiter_available(self, recruiter_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if recruiter is available for the given time period."""
        recruiter = self.recruiters[recruiter_id]
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        for availability_slot in recruiter.availability:
            if (availability_slot.start <= start_time and 
                end_time <= availability_slot.end):
                return True
        return False
        
    def _is_room_available(self, room_id: str, start_time: datetime, duration_minutes: int) -> bool:
        """Check if room is available for the given time period."""
        room = self.rooms[room_id]
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        for availability_slot in room.availability:
            if (availability_slot.start <= start_time and 
                end_time <= availability_slot.end):
                return True
        return False
        
    def _get_available_recruiters(self, start_time: datetime, duration: int) -> List[str]:
        """Get list of available recruiters for given time."""
        available = []
        for recruiter_id in self.recruiters:
            if ((start_time, recruiter_id) not in self.recruiter_schedule and
                self._is_recruiter_available(recruiter_id, start_time, duration)):
                available.append(recruiter_id)
        return available
        
    def generate_reports(self):
        """Generate all required reports."""
        print("\nGenerating reports...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.results_dir, f"run_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        
        self._generate_main_schedule(run_dir)
        self._generate_unscheduled_report(run_dir)
        self._generate_block_breakdown(run_dir)
        self._generate_recruiter_schedule(run_dir)
        self._generate_applicant_schedule(run_dir)
        self._generate_summary_report(run_dir)
        
        print(f"Reports generated in: {run_dir}")
        return run_dir
        
    def _generate_main_schedule(self, output_dir):
        """Generate the main schedule file."""
        filepath = os.path.join(output_dir, 'main_schedule.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Type', 'Start Time', 'End Time', 'Room', 'Applicants', 'Recruiters'])
            
            sorted_interviews = sorted(self.scheduled_interviews, key=lambda x: x.time_slot.start)
            
            for interview in sorted_interviews:
                applicant_names = [self.applicants[app_id].name for app_id in interview.applicants]
                recruiter_names = [self.recruiters[rec_id].name for rec_id in interview.recruiters]
                
                writer.writerow([
                    interview.type,
                    interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                    interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                    interview.room,
                    '; '.join(applicant_names),
                    '; '.join(recruiter_names)
                ])
                
    def _generate_unscheduled_report(self, output_dir):
        """Generate report of unscheduled applicants."""
        filepath = os.path.join(output_dir, 'unscheduled_applicants.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Applicant ID', 'Name', 'Email', 'Teams Interested', 'Has Group', 'Has Individual'])
            
            for applicant_id in self.unscheduled_applicants:
                applicant = self.applicants[applicant_id]
                has_group = applicant_id in self.applicant_group_scheduled
                has_individual = applicant_id in self.applicant_individual_scheduled
                
                writer.writerow([
                    applicant_id,
                    applicant.name,
                    applicant.email,
                    '; '.join(applicant.teams),
                    has_group,
                    has_individual
                ])
                
    def _generate_block_breakdown(self, output_dir):
        """Generate block breakdown for admins."""
        filepath = os.path.join(output_dir, 'block_breakdown.txt')
        
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write("INTERVIEW BLOCK BREAKDOWN\n")
            file.write("=" * 50 + "\n\n")
            
            time_blocks = defaultdict(list)
            for interview in self.scheduled_interviews:
                time_key = interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p')
                time_blocks[time_key].append(interview)
            
            for time_key in sorted(time_blocks.keys()):
                file.write(f"TIME BLOCK: {time_key}\n")
                file.write("-" * 30 + "\n")
                
                for interview in time_blocks[time_key]:
                    file.write(f"  {interview.type.upper()} INTERVIEW - Room {interview.room}\n")
                    
                    applicant_names = [self.applicants[app_id].name for app_id in interview.applicants]
                    file.write(f"    Applicants: {', '.join(applicant_names)}\n")
                    
                    recruiter_names = [self.recruiters[rec_id].name for rec_id in interview.recruiters]
                    file.write(f"    Recruiters: {', '.join(recruiter_names)}\n")
                    file.write("\n")
                
                file.write("\n")
                
    def _generate_recruiter_schedule(self, output_dir):
        """Generate individual schedules for each recruiter."""
        filepath = os.path.join(output_dir, 'recruiter_schedules.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Recruiter', 'Start Time', 'End Time', 'Room', 'Interview Type', 'Applicants'])
            
            recruiter_schedules = defaultdict(list)
            for interview in self.scheduled_interviews:
                for recruiter_id in interview.recruiters:
                    recruiter_schedules[recruiter_id].append(interview)
            
            for recruiter_id in sorted(recruiter_schedules.keys()):
                recruiter = self.recruiters[recruiter_id]
                interviews = sorted(recruiter_schedules[recruiter_id], key=lambda x: x.time_slot.start)
                
                for interview in interviews:
                    applicant_names = [self.applicants[app_id].name for app_id in interview.applicants]
                    
                    writer.writerow([
                        recruiter.name,
                        interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                        interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                        interview.room,
                        interview.type,
                        '; '.join(applicant_names)
                    ])
                    
    def _generate_applicant_schedule(self, output_dir):
        """Generate individual schedules for each applicant."""
        filepath = os.path.join(output_dir, 'applicant_schedules.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Applicant', 'Start Time', 'End Time', 'Room', 'Interview Type', 'Recruiters'])
            
            applicant_schedules = defaultdict(list)
            for interview in self.scheduled_interviews:
                for applicant_id in interview.applicants:
                    applicant_schedules[applicant_id].append(interview)
            
            for applicant_id in sorted(applicant_schedules.keys()):
                applicant = self.applicants[applicant_id]
                interviews = sorted(applicant_schedules[applicant_id], key=lambda x: x.time_slot.start)
                
                for interview in interviews:
                    recruiter_names = [self.recruiters[rec_id].name for rec_id in interview.recruiters]
                    
                    writer.writerow([
                        applicant.name,
                        interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                        interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                        interview.room,
                        interview.type,
                        '; '.join(recruiter_names)
                    ])
                    
    def _generate_summary_report(self, output_dir):
        """Generate summary report."""
        filepath = os.path.join(output_dir, 'summary_report.txt')
        
        total_applicants = len(self.applicants)
        group_scheduled = len(self.applicant_group_scheduled)
        individual_scheduled = len(self.applicant_individual_scheduled)
        fully_scheduled = len(self.applicant_group_scheduled.intersection(self.applicant_individual_scheduled))
        
        group_interviews = len([i for i in self.scheduled_interviews if i.type == 'group'])
        individual_interviews = len([i for i in self.scheduled_interviews if i.type == 'individual'])
        
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write("INTERVIEW SCHEDULING SUMMARY REPORT\n")
            file.write("=" * 50 + "\n\n")
            
            file.write(f"Total Applicants: {total_applicants}\n")
            file.write(f"Fully Scheduled (both interviews): {fully_scheduled}\n")
            file.write(f"Group Interview Only: {group_scheduled - fully_scheduled}\n")
            file.write(f"Individual Interview Only: {individual_scheduled - fully_scheduled}\n")
            file.write(f"Completely Unscheduled: {len(self.unscheduled_applicants)}\n")
            file.write(f"Overall Success Rate: {(fully_scheduled / total_applicants) * 100:.1f}%\n\n")
            
            file.write(f"Total Interviews Scheduled: {len(self.scheduled_interviews)}\n")
            file.write(f"Group Interviews: {group_interviews}\n")
            file.write(f"Individual Interviews: {individual_interviews}\n\n")
            
            file.write("ALGORITHM USED: Greedy Scheduling\n")
            file.write("- Prioritizes group interviews first\n")
            file.write("- Uses first-fit approach for resource allocation\n")
            file.write("- Relaxed constraints for initial feasibility\n\n")


def main():
    """Main function to run the simplified autoscheduler."""
    inputs_dir = "inputs"
    results_dir = "results"
    
    print("=== LUMA Interview Auto-Scheduler (Simplified) ===")
    print()
    
    scheduler = SimpleScheduler(inputs_dir, results_dir)
    
    try:
        scheduler.load_data()
        success = scheduler.schedule_interviews()
        
        if success:
            output_dir = scheduler.generate_reports()
            print(f"\nScheduling complete! Check results in: {output_dir}")
        else:
            print("ERROR: Could not schedule any interviews.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
