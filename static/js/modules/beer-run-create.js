const BEER_RUN_NAME_PATTERN = /^[A-Za-z0-9 _-]{3,64}$/;

export function validateBeerRunName(value) {
    const name = typeof value === 'string' ? value.trim() : '';
    if (!name) {
        return { valid: false, name, message: 'Enter a name for your beer run.' };
    }
    if (!BEER_RUN_NAME_PATTERN.test(name)) {
        return {
            valid: false,
            name,
            message: 'Use 3-64 characters: letters, numbers, spaces, underscores, or hyphens.',
        };
    }
    return { valid: true, name };
}

export function isCreatedBeerRunResponse(run, expectedName, expectedPublic = false) {
    return Boolean(
        run
        && Number.isInteger(Number(run.id))
        && Number(run.id) > 0
        && typeof run.name === 'string'
        && run.name === expectedName
        && run.is_public === expectedPublic
        && Number(run.member_count) === 1
        && run.current_user_role === 'owner'
        && typeof run.created_at === 'string'
        && run.created_at.length > 0
    );
}
