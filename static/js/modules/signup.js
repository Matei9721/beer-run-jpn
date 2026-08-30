/**
 * Client-side account-creation logic: local field validation and readable,
 * secret-safe rendering of server failures.
 *
 * These helpers never touch the DOM or network. The auth module owns the modal
 * UI and the api module owns the request; this file only decides what is valid
 * and what the user should be told.
 */

const USERNAME_PATTERN = /^[A-Za-z0-9_-]+$/;
const PASSWORD_LETTER_PATTERN = /[A-Za-z]/;
const PASSWORD_DIGIT_PATTERN = /[0-9]/;

const FIELD_LABELS = {
    username: 'Username',
    password: 'Password',
    signup_code: 'Signup code',
    terms_agreed: 'Terms agreement',
    terms_version: 'Terms version',
};

/**
 * Validate signup input before any request is made.
 *
 * Returns the trimmed username (the only value normalized to match the API)
 * plus a field-keyed error map. Passwords and signup codes are never echoed
 * back in error text.
 */
export function validateSignupFields({ username, password, confirmPassword, signupCode, termsAccepted }) {
    const trimmedUsername = username.trim();
    const errors = {};

    if (!trimmedUsername) {
        errors.username = 'Username is required.';
    } else if (trimmedUsername.length < 3 || trimmedUsername.length > 32) {
        errors.username = 'Username must be 3-32 characters.';
    } else if (!USERNAME_PATTERN.test(trimmedUsername)) {
        errors.username = 'Username may only contain letters, numbers, underscores, and hyphens.';
    }

    if (!password) {
        errors.password = 'Password is required.';
    } else if (password.length < 8) {
        errors.password = 'Password must be at least 8 characters.';
    } else if (!PASSWORD_LETTER_PATTERN.test(password) || !PASSWORD_DIGIT_PATTERN.test(password)) {
        errors.password = 'Password must include at least one letter and one number.';
    }

    if (!confirmPassword) {
        errors.confirmPassword = 'Please confirm your password.';
    } else if (password !== confirmPassword) {
        errors.confirmPassword = 'Passwords do not match.';
    }

    if (!signupCode.trim()) {
        errors.signupCode = 'Signup code is required.';
    }

    if (!termsAccepted) {
        errors.termsAccepted = 'You must be at least 18 and agree to the Terms of Service.';
    }

    return {
        valid: Object.keys(errors).length === 0,
        username: trimmedUsername,
        errors,
    };
}

/** Join field errors into a single readable block of text. */
export function formatValidationErrors(errors) {
    return Object.values(errors).join('\n');
}

/**
 * Map an unsuccessful signup response to a readable message.
 *
 * Only known, sanitized API detail text is reused. Any unexpected body shape
 * falls back to a generic message so nothing secret leaks to the user.
 */
export async function getSignupFailureMessage(response) {
    let detail = null;
    try {
        const body = await response.json();
        detail = body && body.detail;
    } catch (error) {
        // Non-JSON body; fall through to the generic message below.
    }

    if (response.status === 409) {
        return 'Username already exists.';
    }
    if (response.status === 403) {
        return 'Invalid signup code. Please check the code and try again.';
    }
    if (response.status === 422) {
        if (typeof detail === 'string' && detail) {
            return detail;
        }
        if (Array.isArray(detail)) {
            const parts = detail
                .filter(entry => entry && entry.msg)
                .map(entry => {
                    const loc = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : null;
                    const label = FIELD_LABELS[loc] || 'Account';
                    return `${label}: ${entry.msg}`;
                });
            if (parts.length) {
                return parts.join('\n');
            }
        }
        return 'Please check your details and try again.';
    }
    return 'Unable to create account. Please try again.';
}
