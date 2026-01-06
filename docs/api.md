# API Reference

## Authentication

All endpoints except the admin panel require the `X-API-Key` header.

The admin panel uses cookie-based authentication.

---

## Documents

### POST /documents

Upload a PDF summary.

**Request:**
- Content-Type: multipart/form-data
- file: PDF file
- subject_id: uuid (optional)
- teacher_id: uuid (optional)

**Response:**
```json
{
  "id": "uuid",
  "filename": "lecture.pdf",
  "status": "pending",
  "created_at": "2025-01-06T12:00:00Z"
}
```

### GET /documents

List all documents.

**Response:**
```json
[
  {
    "id": "uuid",
    "filename": "lecture.pdf",
    "subject_id": "uuid",
    "teacher_id": "uuid",
    "status": "ready",
    "created_at": "2025-01-06T12:00:00Z"
  }
]
```

### GET /documents/{id}

Get document details and processing progress.

**Response:**
```json
{
  "id": "uuid",
  "filename": "lecture.pdf",
  "subject_id": "uuid",
  "teacher_id": "uuid",
  "s3_key": "documents/uuid.pdf",
  "status": "processing",
  "current_page": 5,
  "total_pages": 20,
  "error": null,
  "created_at": "2025-01-06T12:00:00Z",
  "processed_at": null
}
```

### PATCH /documents/{id}

Update document metadata.

**Request:**
```json
{
  "subject_id": "uuid",
  "teacher_id": "uuid"
}
```

**Response:**
```json
{
  "id": "uuid",
  "subject_id": "uuid",
  "teacher_id": "uuid",
  "updated_at": "2025-01-06T12:00:00Z"
}
```

### DELETE /documents/{id}

Delete a document, the file from S3, and associated chunks from Qdrant.

**Response:**
```json
{
  "deleted": true
}
```

---

## Solve

### POST /solve

Submit a problem to solve.

**Request:**
```json
{
  "question": "Find the derivative of f(x) = x^2 + 3x",
  "subject_filter": "calculus Ivanov 2nd year"
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "pending",
  "created_at": "2025-01-06T12:00:00Z"
}
```

### GET /solve/{id}

Get the status and result of a solve request.

**Response:**
```json
{
  "id": "uuid",
  "question": "Find the derivative of f(x) = x^2 + 3x",
  "subject_filter": "calculus Ivanov 2nd year",
  "matched_subject_id": "uuid",
  "matched_teacher_id": "uuid",
  "answer": "Solution: f'(x) = 2x + 3...",
  "used_rag": true,
  "verified": true,
  "status": "ready",
  "error": null,
  "created_at": "2025-01-06T12:00:00Z",
  "processed_at": "2025-01-06T12:00:05Z"
}
```

### GET /solve

List of solve requests history.

**Query params:**
- limit: int (default 20)
- offset: int (default 0)

**Response:**
```json
[
  {
    "id": "uuid",
    "question": "Find the derivative...",
    "status": "ready",
    "used_rag": true,
    "verified": true,
    "created_at": "2025-01-06T12:00:00Z"
  }
]
```

---

## Subjects

### GET /subjects

Get the list of subjects.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Mathematical Analysis",
    "course": 1,
    "created_at": "2025-01-06T12:00:00Z"
  }
]
```

### POST /subjects

Create a subject.

**Request:**
```json
{
  "name": "Mathematical Analysis",
  "course": 1
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Mathematical Analysis",
  "course": 1,
  "created_at": "2025-01-06T12:00:00Z"
}
```

### PATCH /subjects/{id}

Update a subject.

**Request:**
```json
{
  "name": "Calculus",
  "course": 2
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Calculus",
  "course": 2,
  "updated_at": "2025-01-06T12:00:00Z"
}
```

### DELETE /subjects/{id}

Delete a subject.

**Response:**
```json
{
  "deleted": true
}
```

---

## Teachers

### GET /teachers

Get a list of teachers.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Ivanov Ivan Ivanovich",
    "created_at": "2025-01-06T12:00:00Z"
  }
]
```

### POST /teachers

Create a teacher.

**Request:**
```json
{
  "name": "Ivanov Ivan Ivanovich"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Ivanov Ivan Ivanovich",
  "created_at": "2025-01-06T12:00:00Z"
}
```

### PATCH /teachers/{id}

Update a teacher.

**Request:**
```json
{
  "name": "Ivanov I.I."
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Ivanov I.I.",
  "updated_at": "2025-01-06T12:00:00Z"
}
```

### DELETE /teachers/{id}

Delete a teacher.

**Response:**
```json
{
  "deleted": true
}
```

---

## Status Codes

| Code | Description            |
|------|------------------------|
| 200  | OK                     |
| 201  | Created                |
| 400  | Bad Request            |
| 401  | Unauthorized           |
| 404  | Not Found              |
| 500  | Internal Server Error  |
