from models import db

class Obituary(db.Model):
    __tablename__ = 'obituaries'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.String(20))
    date_of_death = db.Column(db.String(20))
    biography = db.Column(db.Text)
    funeral_details = db.Column(db.Text)
    photo = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Obituary {self.full_name}>'