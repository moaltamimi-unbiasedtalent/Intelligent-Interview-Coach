export const STATUS_LABEL: Record<string, string> = {
  submitted: "Submitted", acknowledged: "Acknowledged", in_progress: "In progress", waiting_for_user: "Waiting for the candidate",
  completed: "Completed", closed: "Closed", rejected: "Rejected",
};
export const TYPE_LABEL: Record<string, string> = {
  data_access: "Data access or export", deletion: "Account or data deletion", correction: "Correction of my data",
  consent_question: "Question about a consent or preference", other_privacy: "Other privacy question",
};
export const RESULT_LABEL: Record<string, string> = {
  export_provided: "Export provided (the candidate used self-service export)", deletion_performed: "Deletion performed",
  correction_made: "Correction made", information_provided: "Information provided", no_action_required: "No action required",
  unable_to_verify: "Unable to verify the request",
};
export const label = (v: string) => v.replace(/_/g, " ");
