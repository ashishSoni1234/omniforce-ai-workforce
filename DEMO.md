# 🚀 OmniForce AI Workforce - Live Demo

Welcome to the **OmniForce AI Workforce** demo! Below is a visual walkthrough of the three autonomous agents executing complex financial operations in real-time.

---

## 🎯 1. Sales Agent (CRM Automation)
The Sales Agent is responsible for autonomous lead generation. It fetches targeted leads from the web based on specific queries, parses their data, and injects them directly into the Airtable CRM system.

![Sales Agent Instruction](images/Screenshot%202026-05-11%20025251.png)
*Entering instructions to find targeted fintech companies in London.*

![Sales Agent Output](images/Screenshot%202026-05-11%20025259.png)
*Agent successfully parses the web and identifies 5 qualified leads.*

![Sales CRM Sync](images/Screenshot%202026-05-11%20025307.png)
*The leads are successfully formatted and automatically appended to the Airtable CRM.*

![Sales CRM Dashboard](images/Screenshot%202026-05-11%20025314.png)
*Dashboard view confirming the leads are properly mapped to the correct columns (Revenue, Founded, Stage).*

---

## ⚙️ 2. Ops Agent (Invoice & Anomaly Detection)
The Ops Agent automates the processing of financial documents. It extracts data, checks for anomalies (like unusually high expenses or offshore vendors), and routes the document for approval based on the risk level.

![Ops Agent Input](images/Screenshot%202026-05-11%20025523.png)
*Feeding an invoice containing an offshore vendor and high miscellaneous fees into the Ops Agent.*

![Ops Agent Analysis](images/Screenshot%202026-05-11%20025531.png)
*The Agent successfully flags the high-risk anomalies and routes the approval to a Manager.*

---

## 🔍 3. KYC Agent (Risk & Compliance Verification)
The KYC Agent handles "Know Your Customer" compliance. Utilizing **Hugging Face Cloud Embeddings** and ChromaDB, it scans baseline regulatory rules to verify if the provided documents are sufficient.

![KYC Agent Input](images/Screenshot%202026-05-11%20032614.png)
*Submitting a new client for a compliance check (intentionally omitting Proof of Address).*

![KYC Agent Processing](images/Screenshot%202026-05-11%20032627.png)
*The Agent cross-references the documents with RAG compliance rules.*

![KYC Agent Output](images/Screenshot%202026-05-11%20032634.png)
*The Agent flags the missing documents, assigns a Medium risk level, and automatically sends an email to the client.*

---
*Built with LangGraph, Groq, ChromaDB, and Hugging Face Inference API.*
