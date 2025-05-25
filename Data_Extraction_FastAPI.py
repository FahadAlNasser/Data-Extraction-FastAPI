from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import requests
import fitz
import re

The_Database_url = "sqlite:///./reports.db"
Structure = declarative_base()
engine = create_engine(The_Database_url, connect_args={"check_same_thread": False})
Sessions = sessionmaker(bind=engine)

class Insight(Structure):
    __tablename__ = "insight"
    id = Column(Integer, primary_key = True, index=True)
    comp = Column(String, unique=True, index=True)
    link = Column(String)
    word = Column(String)

Structure.metadata.create_all(bind=engine)
app = FastAPI()

Sustainability = {
    "Aramco": "https://www.aramco.com/-/media/publications/corporate-reports/sustainability-reports/report-2023/english/2023-saudi-aramco-sustainability-report-full-en.pdf",
    "STC": "https://www.stc.com/content/dam/groupsites/en/pdf/stc-sustainability-report2023englishV2.pdf",
    "Microsoft": "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/msc/documents/presentations/CSR/Microsoft-2024-Environmental-Sustainability-Report.pdf",
    "Apple": "https://www.apple.com/environment/pdf/Apple_Environmental_Progress_Report_2025.pdf",
    "Google": "https://www.gstatic.com/gumdrop/sustainability/google-2024-environmental-report.pdf"
}


@app.post("/filling")
def filling_reports():
   database = Sessions()
   try:
      for comp, link in Sustainability.items():
        response = requests.get(link)
        if response.status_code != 200:
           continue
        with open(f"{comp}.pdf", "wb") as file:
           file.write(response.content)
        f = fitz.open(f"{comp}.pdf")
        complete_text = ""
        for pg in f:
           complete_text += pg.get_text()
        f.close()
        authen = database.query(Insight).filter(Insight.comp == comp).first()
        if authen:
           authen.word = complete_text
        else:
           recent_input = Insight(comp=comp, link=link, word=complete_text)
           database.add(recent_input)
      database.commit()
      return {"message":"Download completed"}
   except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))
   finally:
      database.close()


@app.get("/insight")
def get_insight():
    database = Sessions()
    try:
        insights = database.query(Insight).all()
        return  [{
            "comp": r.comp,
            "link": r.link,
            "word_sample": r.word[:200] if r.word else ""
        } for r in insights]
    except Exception:
        raise HTTPException(status_code=500, detail="It has failed to fetch the report")
    finally:
        database.close()

@app.get("/finding-paragraphs")
def finding_paragraphs(comp: str, keyword: str = Query(..., min_length=2)):
    database = Sessions()
    try:
      insight = database.query(Insight).filter(Insight.comp == comp).first()
      if not insight or not insight.word:
        raise HTTPException(status_code=404, detail="Report not found or empty")
      parag = re.split(r'\n\s*\n', insight.word)
      discovery = []
      keyword_lower = keyword.lower()

      for par in parag:
        par_lower = par.lower()
        if keyword_lower in par_lower:
          percentages = re.findall(r'\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*percent', par, flags=re.IGNORECASE)
          discovery.append({
              "Paragraph": par.strip(),
              "Percentages": percentages
              })
      return {"comp": comp, "keyword": keyword, "matches": discovery[:10]}
    finally:
      database.close()
