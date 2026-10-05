const test = require("node:test");
const assert = require("node:assert/strict");
const { isInternshipJob } = require("../src/lib/job-categories.cjs");

test("recognizes common internship and student-role titles across locales", () => {
  for (const title of ["Software Engineering Intern", "Internship - Data", "Working Student - QA", "Traineeship", "Praktikum Software", "Werkstudent IT", "Stajyer Yazılım Geliştirici"]) {
    assert.equal(isInternshipJob({ title }), true, title);
  }
});

test("does not classify permanent roles just because they contain internal", () => {
  assert.equal(isInternshipJob({ title: "Internal Tools Engineer" }), false);
  assert.equal(isInternshipJob({ title: "Senior Software Engineer" }), false);
});

test("recognizes structured role type and source tags", () => {
  assert.equal(isInternshipJob({ title: "Student Associate", job_type: "internship" }), true);
  assert.equal(isInternshipJob({ title: "Developer", source_tags: ["co-op"] }), true);
});
