/** Single-user MVP — hardcoded patient identity.
 *
 * Replace this file with a proper user-table / auth lookup once we have
 * one. Fields here are the only ones the UI is allowed to assume; if it
 * isn't on this object, the panel must hide that row rather than fake it.
 */

export interface PatientIdentity {
  full_name: string;
  preferred_name: string;
}

export const PATIENT: PatientIdentity = {
  full_name: "Doruk YILDIRIM",
  preferred_name: "Doruk",
};
