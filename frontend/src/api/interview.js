import client from "./client";

export function createReport({ resume, jobDescription, selfDescription }) {
  const form = new FormData();
  form.append("resume", resume);
  form.append("job_description", jobDescription);
  form.append("self_description", selfDescription || "");
  // Do not set Content-Type manually: the browser must set the multipart
  // boundary itself, and axios/fetch get this wrong if you override it.
  return client.post("/interview/", form).then((r) => r.data);
}

export function listReports(limit = 20, offset = 0) {
  return client.get("/interview/", { params: { limit, offset } }).then((r) => r.data);
}

export function getReport(id) {
  return client.get(`/interview/${id}`).then((r) => r.data);
}

export function deleteReport(id) {
  return client.delete(`/interview/${id}`).then((r) => r.data);
}

export function downloadReportPdf(id) {
  return client
    .post(`/interview/${id}/pdf`, null, { responseType: "blob" })
    .then((r) => r.data)
    .catch(async (err) => {
      // With responseType "blob" an error body arrives as a Blob too, so
      // messageForError would never see its code. Parse it back to JSON.
      const data = err.response?.data;
      if (data instanceof Blob) {
        try {
          err.response.data = JSON.parse(await data.text());
        } catch {
          // Not JSON (a proxy error page, say); leave it for the fallback.
        }
      }
      throw err;
    });
}

export function suggestCareers(resume) {
  const form = new FormData();
  form.append("resume", resume);
  return client.post("/interview/careers", form).then((r) => r.data);
}
