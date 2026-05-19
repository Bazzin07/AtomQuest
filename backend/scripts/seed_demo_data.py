import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User, UserRole
from app.models.goal import GoalCycle, ThrustArea, Goal, GoalStatus, ProgressStatus
from app.models.checkin import CheckinWindow, CheckinComment
from app.services.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

fake = Faker()

async def clear_existing(session):
    # Depending on DB constraints, clearing everything might require cascading or dropping.
    # For a simple demo seed, we might just keep appending or optionally clear.
    pass

async def seed_data():
    async with async_session_factory() as session:
        # 1. Create Core Users if they don't exist
        logger.info("Seeding Users...")
        admin = User(
            email="admin@atomquest.app",
            hashed_password=get_password_hash("Admin@123"),
            full_name="System Admin",
            role=UserRole.ADMIN,
            is_active=True
        )
        manager = User(
            email="manager@atomquest.app",
            hashed_password=get_password_hash("Manager@123"),
            full_name="Project Manager",
            role=UserRole.MANAGER,
            is_active=True
        )
        employee = User(
            email="employee@atomquest.app",
            hashed_password=get_password_hash("Employee@123"),
            full_name="Field Employee",
            role=UserRole.EMPLOYEE,
            is_active=True
        )
        
        # Check if exists
        result = await session.execute(select(User).where(User.email == "admin@atomquest.app"))
        if not result.scalar_one_or_none():
            session.add_all([admin, manager, employee])
            await session.commit()
        else:
            admin = (await session.execute(select(User).where(User.email == "admin@atomquest.app"))).scalar_one()
            manager = (await session.execute(select(User).where(User.email == "manager@atomquest.app"))).scalar_one()
            employee = (await session.execute(select(User).where(User.email == "employee@atomquest.app"))).scalar_one()

        # Add 10 random employees
        employees = [employee]
        for _ in range(10):
            emp = User(
                email=fake.email(),
                hashed_password=get_password_hash("Password123!"),
                full_name=fake.name(),
                role=UserRole.EMPLOYEE,
                is_active=True
            )
            session.add(emp)
            employees.append(emp)
        await session.commit()

        # 2. Create Cycles
        logger.info("Seeding Cycles...")
        cycle1 = GoalCycle(
            name="FY2025 H1",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 30, tzinfo=timezone.utc),
            is_active=False
        )
        cycle2 = GoalCycle(
            name="FY2025 H2",
            start_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
            is_active=True
        )
        session.add_all([cycle1, cycle2])
        await session.commit()

        # 3. Create Thrust Areas
        logger.info("Seeding Thrust Areas...")
        thrust_areas = []
        for name in ["Revenue Growth", "Operational Excellence", "Customer Success", "Product Innovation", "Security & Compliance"]:
            ta = ThrustArea(name=name, description=fake.catch_phrase())
            session.add(ta)
            thrust_areas.append(ta)
        await session.commit()

        # 4. Create Goals (100+)
        logger.info("Seeding Goals...")
        goals = []
        for i in range(150):
            emp = random.choice(employees)
            status = random.choices(
                [GoalStatus.DRAFT, GoalStatus.IN_REVIEW, GoalStatus.APPROVED],
                weights=[10, 20, 70]
            )[0]
            
            goal = Goal(
                title=fake.sentence(nb_words=6),
                description=fake.paragraph(),
                owner_id=emp.id,
                manager_id=manager.id,
                cycle_id=cycle2.id,
                thrust_area_id=random.choice(thrust_areas).id,
                status=status,
                weightage=random.randint(5, 20),
                target_value=random.randint(10, 1000),
                current_value=0, # will be updated by check-ins
                progress_status=ProgressStatus.ON_TRACK,
            )
            session.add(goal)
            goals.append(goal)
        await session.commit()

        # 5. Create Checkin Windows
        logger.info("Seeding Checkin Windows...")
        now = datetime.now(timezone.utc)
        cw1 = CheckinWindow(
            cycle_id=cycle2.id,
            start_date=now - timedelta(days=7),
            end_date=now + timedelta(days=7),
            is_open=True
        )
        session.add(cw1)
        await session.commit()

        # 6. Create Checkins
        logger.info("Seeding Checkins...")
        for goal in goals:
            if goal.status == GoalStatus.APPROVED:
                # Add 1-5 checkins
                num_checkins = random.randint(1, 5)
                cumulative = 0
                for _ in range(num_checkins):
                    inc = random.randint(1, int(goal.target_value / num_checkins) + 1)
                    cumulative += inc
                    if cumulative > goal.target_value:
                        cumulative = goal.target_value
                    
                    chk = CheckinComment(
                        goal_id=goal.id,
                        user_id=goal.owner_id,
                        window_id=cw1.id,
                        comment=fake.sentence(),
                        value_achieved=cumulative,
                        progress_status=random.choices([ProgressStatus.ON_TRACK, ProgressStatus.AT_RISK, ProgressStatus.BEHIND], weights=[70, 20, 10])[0]
                    )
                    session.add(chk)
                
                goal.current_value = cumulative
                session.add(goal)
        
        await session.commit()
        logger.info("Data seeding completed successfully! ✨")

if __name__ == "__main__":
    asyncio.run(seed_data())
