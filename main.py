import csv
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from pydantic import Field, BaseModel
from flask_openapi3 import Info, Tag, OpenAPI, FileStorage


info = Info(title="Color Storing API", version="1.0.0", description="A simple API to store colors in a SQLite database")

app = OpenAPI(__name__, info=info, validation_error_status=400)
app.config["UPLOAD_FOLDER"] = "./uploads"
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///csv_data.db'
app.config["REQUIREMENTS"] = {0: int, 1: str, 2: str, 3: int, 4: int, 5: int, 6: int}
app.config["PAGINATION"] = 4

writer_tag = Tag(name="Write Objects", description="View the page to upload the file or directly POST the file")
reader_tag = Tag(name="Read Objects", description="View the objects on database")


class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

class Color(db.Model):
    _id = db.Column("_id", db.Integer, primary_key=True) # in this scenario id is set manually in order to avoid duplications
    
    _name = db.Column(db.String(50), nullable=False) 
    
    hex = db.Column(db.String(6), nullable=False)
    
    red = db.Column(db.Integer, nullable=False)
    green = db.Column(db.Integer, nullable=False)
    blue = db.Column(db.Integer, nullable=False)
    
    decimal = db.Column(db.Integer, nullable=False)
    
    def __init__(self, _id, _name, hex, red, green, blue, decimal):
        self._id = _id 
        self._name = _name
        self.hex = hex
        self.red = red
        self.green = green
        self.blue = blue
        self.decimal = decimal
        
    def to_json(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    
    
class CSVFileUpload(BaseModel):
    file: FileStorage
    
@app.post('/write-objects/', 
          tags=[writer_tag], 
          summary="POST /write-objects",
          description="Upload a CSV file with the following format: id(int);name(str);hex(str);red(int);green(int);blue(int);decimal(int)",
          responses={200: {'description': 'OK'}, 
                    400: {'description': 'Bad Request'}})
def write_objects(form: CSVFileUpload):
    file = form.file
    
    if file.filename == '' or not file and not file.filename.endswith('.csv'):
        return 'Invalid file format', 400
        
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    with open(file_path, 'r', encoding='utf-8-sig') as file: # utf-8-sig is used to remove the BOM character
        file.seek(0)
        reader = csv.reader(file)
        for row in reader:
            row: str = row[0]
            cols = row.split(';')
            
            if len(cols) != len(app.config['REQUIREMENTS'].keys()):
                os.remove(file_path)
                return 'An error occured with the file', 400
            
            for k, v in app.config['REQUIREMENTS'].items():
                try:
                    cols[k] = v(cols[k])
                except:
                    os.remove(file_path)
                    return 'Encountered invalid data type', 400
            
            if Color.query.filter_by(_id=cols[0]).first():
                os.remove(file_path)
                return 'Avoided duplicate id entry', 400
            
            color = Color(*cols)
            db.session.add(color)
            db.session.commit()
    
    os.remove(file_path)
        
    return 'File uploaded successfully, GET /read-objects/', 200
    

class PageQuery(BaseModel):
    page: int = Field(description="Page number to be read", default=1)

@app.get('/read-objects/', 
         tags=[reader_tag], 
         summary="GET /read-objects",
         description=f"Read the objects on the database, {app.config["PAGINATION"]} per page.",
         responses={200: {'description': 'OK'}, 
                    400: {'description': 'Bad Request'},
                    404: {'description': 'Out of Bounds'}},
         )
def read_objects(query: PageQuery):
    page = query.page
    data = Color.query.all()
    finalData = [data[x:x+app.config["PAGINATION"]] for x in range(0, len(data), app.config["PAGINATION"])]
    
    if page > len(finalData) or page < 1:
        return 'Page out of bounds', 404
    
    return [x.to_json() for x in finalData[page-1]], 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5000, host="0.0.0.0")