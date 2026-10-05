const INTERNSHIP_TITLE_PATTERN = /\bintern(?:ship)?s?\b|\bworking student\b|\bstudent placement\b|\btrainee(?:ship)?\b|\bco[\s-]?op\b|\bpraktikum\b|\bwerkstudent\b|\bpraktik(?:ant|a)\b|\bstaj(?:yer)?\b/;

function isInternshipJob(job) {
  const tags = Array.isArray(job?.source_tags)
    ? job.source_tags.join(" ")
    : (job?.source_tags || "");
  const titleAndTags = `${job?.title || ""} ${job?.job_type || ""} ${tags}`
    .normalize("NFKD")
    .toLowerCase();
  return INTERNSHIP_TITLE_PATTERN.test(titleAndTags);
}

module.exports = { isInternshipJob };
