from app.db.session import engine
from app.db import models

print("Creating tables...")
models.Base.metadata.create_all(bind=engine)
print("Done.")


models.Base.metadata.create_all(bind=engine)
