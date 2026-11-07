from datetime import datetime, timedelta


class AirportError(Exception):
    """Raised when an airport rule is broken."""


class Employee:
    def __init__(self, name, employee_id, role, available=True):
        if not name or not employee_id:
            raise ValueError("Name and employee ID must not be empty")
        self._name = name
        self._employee_id = employee_id
        self._role = role
        self.available = available

    def __str__(self):
        return (f"Employee: {self._name}, {self._employee_id}, {self._role}, "
               f"{self._available}")

    @property
    def employee_id(self):
        return self._employee_id

    @property
    def role(self):
        return self._role

    @property
    def available(self):
        return self._available

    @available.setter
    def available(self, value):
        if not isinstance(value, bool):
            raise TypeError("Availability must be True or False")
        self._available = value


class RampAgent(Employee):
    def __init__(self, name, employee_id, available=True):
        super().__init__(name, employee_id, "Ramp Agent", available)
        self._task = None

    def get_task(self):
        return self._task

    def assign_task(self, task):
        if not self.available:
            raise AirportError("Employee not available!")
        self._task = task
        self.available = False
        return True

    def complete_task(self):
        if self._task is None:
            raise AirportError("Ramp agent has no task assigned currently!")
        self._task = None
        self.available = True
        return True


class TeamLeader(Employee):
    def __init__(self, name, employee_id, available=True):
        super().__init__(name, employee_id, "Team Leader", available)

    def assign_task(self, ramp_agent, task):
        return ramp_agent.assign_task(task)

    def approve_crew(self, crew):
        if not crew.meets_requirements():
            raise AirportError("Crew does not meet flight requirements!!!")
        if self not in crew.get_members():
            raise AirportError("Warning: flight requires a team leader!")
        return True


class GroundCrew:
    def __init__(self, crew_num):
        self._crew_num = crew_num
        self._members = []

    def add_member(self, employee):
        if len(self._members) >= 4:
            raise AirportError("Crew already has 4 members!")
        if employee in self._members:
            raise AirportError("Employee already in Crew!")

        self._members.append(employee)

    def get_members(self):
        return tuple(self._members)

    def remove_members(self, employee):
        if employee not in self._members:
            raise AirportError("Employee not in team!")
        self._members.remove(employee)

    def meets_requirements(self):
        if len(self._members) != 4:
            return False
        team_lead = 0
        for employee in self._members:
            if type(employee) is TeamLeader:
                team_lead += 1
        return team_lead == 1


class Flight:
    def __init__(self, flight_code, dest, etd):
        if not flight_code or not dest:
            raise ValueError("Flight code and destination cannot be empty")
        if not isinstance(etd, datetime):
            raise TypeError("ETD must be a datetime")
        self._flight_code = flight_code
        self._dest = dest
        self._etd = etd
        self._crew = None
        self._cancelled = False

    @property
    def flight_code(self):
        return self._flight_code

    @property
    def dest(self):
        return self._dest

    @property
    def etd(self):
        return self._etd

    @property
    def crew(self):
        return self._crew

    @property
    def cancelled(self):
        return self._cancelled

    def assign_approved_crew(self, crew):
        if self._crew is not None:
            raise AirportError("Flight has an active team!")

        if not crew.meets_requirements():
            raise AirportError("Crew does not meet requirements")
        self._crew = crew
        return True

    def remove_crew(self):
        if self._crew is None:
            raise AirportError("Flight has no crew to remove")
        self._crew = None

    def delay_flight(self, minutes, hours):
        if minutes < 0 or hours < 0:
            raise ValueError("Delay cannot be negative")
        self._etd += timedelta(minutes=minutes, hours=hours)

    def flight_cancelled(self):
        self._cancelled = True
        self._crew = None


class Airport:
    def __init__(self, name, iata_code):
        self._name = name
        self._iata_code = iata_code
        self._employees = []
        self._flights = []

    def add_employee(self, employee):
        for existing_employee in self._employees:
            if existing_employee.employee_id == employee.employee_id:
                raise AirportError("Staff ID already exists")
        self._employees.append(employee)

    def add_flight(self, flight):
        for existing_flight in self._flights:
            if existing_flight.flight_code == flight.flight_code:
                raise AirportError("Cannot duplicate Flights")
        self._flights.append(flight)

    def find_flight(self, flight_code):
        for flight in self._flights:
            if flight.flight_code == flight_code:
                return flight
        return None

# team leader, 3 employees per flight


def test():
    airport = Airport("Cork Airport", "ORK")

    team_leader = TeamLeader("Jonathan", "808123")
    agent1 = RampAgent("Peter", "807544")
    agent2 = RampAgent("jan", "807545")
    agent3 = RampAgent("Peter", "807546")

    airport.add_employee(team_leader)
    airport.add_employee(agent1)
    airport.add_employee(agent2)
    airport.add_employee(agent3)

    crew = GroundCrew(1)

    crew.add_member(team_leader)
    crew.add_member(agent1)
    crew.add_member(agent2)
    crew.add_member(agent3)

    print(crew.meets_requirements())
    print(team_leader.approve_crew(crew))

    departure = datetime(2026, 10, 11, 14, 30)
    flight = Flight("FR9006", "STN", departure)
    airport.add_flight(flight)
    print(flight.assign_approved_crew(crew))
    flight.delay_flight(hours=2, minutes=38)
    print(flight.etd)

    print("Error handling sample test:)")

    # Crew is already full
    try:
        crew.add_member(RampAgent("Daniel", "807547"))
    except AirportError as error:
        print(f"Error: {error}")

    # Trying to assign task when agent is busy
    agent1.assign_task("Load bags")
    try:
        agent1.assign_task("Refuelling Diesel tugs")
    except AirportError as error:
        print(f"Error: {error}")

    # Empty name
    try:
        RampAgent("", "111115")
    except ValueError as error:
        print(f"Error: {error}")

    # Negative delay
    try:
        flight.delay_flight(minutes=-5, hours=0)
    except ValueError as error:
        print(f"Error: {error}")

    # ETD must be a datetime, not string
    try:
        Flight("EI100", "LHR", "tomorrow")
    except TypeError as error:
        print(f"Error: {error}")

    # Only accepts True or False
    try:
        agent1.available = "yes"
    except TypeError as error:
        print(f"Error: {error}")


test()