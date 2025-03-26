from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy
db = SQLAlchemy()

class Comment(db.Model):
    """
    SQLAlchemy model for storing Notion comments.
    """
    __tablename__ = 'comments'
    
    id = db.Column(db.String(36), primary_key=True)  # Notion comment ID
    discussion_id = db.Column(db.String(36), nullable=True)  # Notion discussion ID
    parent_type = db.Column(db.String(20), nullable=False)  # 'page' or 'block'
    parent_id = db.Column(db.String(36), nullable=False)  # ID of the parent page or block
    created_time = db.Column(db.DateTime, nullable=False)
    last_edited_time = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.String(36), nullable=True)  # User ID who created the comment
    plain_text = db.Column(db.Text, nullable=False)  # The comment text content
    status = db.Column(db.String(20), default='new')  # Status of the comment (new, processed, error)
    processed_at = db.Column(db.DateTime, nullable=True)  # When the comment was processed
    
    def __init__(self, id, parent_type, parent_id, plain_text, discussion_id=None, 
                 created_time=None, last_edited_time=None, created_by_id=None, 
                 status='new'):
        self.id = id
        self.discussion_id = discussion_id
        self.parent_type = parent_type
        self.parent_id = parent_id
        self.plain_text = plain_text
        self.created_time = created_time or datetime.utcnow()
        self.last_edited_time = last_edited_time
        self.created_by_id = created_by_id
        self.status = status
    
    def __repr__(self):
        return f"<Comment {self.id}>"

def init_db(app):
    """
    Initialize the database with the Flask app.
    """
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///notion_comments.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
