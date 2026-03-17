from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

#Async engine creation
engine = create_async_engine(DATABASE_URL, echo=False)

#Session factory
AsyncSessionLocal=sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

#Base class
Base = declarative_base()

#Dependency to get DB session
async def get_db():
    #open a new session and yield it, ensuring it's closed after use
    async with AsyncSessionLocal() as session:
        yield session