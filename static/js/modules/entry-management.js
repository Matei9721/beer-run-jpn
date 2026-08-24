import * as ui from './ui.js?v=13';

function selectedValue(select, customInput, customValue) {
    return select.value === customValue ? customInput.value.trim() : select.value;
}

function hasUpload(file) {
    return file instanceof File && Boolean(file.name) && file.size > 0;
}

function setSelectValue(select, customInput, value, customValue) {
    const normalized = String(value ?? '');
    const option = [...select.options].find(item => (
        item.value === normalized && item.value !== customValue
    ));
    if (option) {
        select.value = option.value;
        customInput.value = '';
    } else {
        select.value = customValue;
        customInput.value = normalized;
    }
}

export function createEntryManagement({
    onCreate,
    onUpdate,
    onDelete,
    onMutationSuccess,
    onCancelEdit,
} = {}) {
    const form = document.getElementById('entry-form');
    const formFields = document.getElementById('entry-form-fields');
    const formTitle = document.getElementById('entry-form-title');
    const formContext = document.getElementById('entry-form-context');
    const formStatus = document.getElementById('entry-form-status');
    const formError = document.getElementById('entry-form-error');
    const createSuccess = document.getElementById('entry-create-success');
    const logAnotherButton = document.getElementById('log-another-entry');
    const submitButton = document.getElementById('submit-btn');
    const cancelEditButton = document.getElementById('cancel-edit-btn');
    const drinkTypeSelect = document.getElementById('drink_type_select');
    const customDrinkType = document.getElementById('custom_drink_type');
    const brandInput = document.getElementById('brand');
    const abvInput = document.getElementById('abv');
    const quantitySelect = document.getElementById('quantity_select');
    const customQuantity = document.getElementById('custom_quantity');
    const imageInput = document.getElementById('image');
    const imageInputWrap = document.getElementById('image-input-wrap');
    const imageLabel = document.getElementById('image-label');
    const editPhotoOptions = document.getElementById('edit-photo-options');
    const currentPhotoState = document.getElementById('current-photo-state');
    const photoKeepLabel = document.getElementById('photo-keep-label');
    const photoRemoveOption = document.getElementById('photo-remove-option');
    const latitudeInput = document.getElementById('latitude');
    const longitudeInput = document.getElementById('longitude');
    const locationButton = document.getElementById('get-location-btn');
    const locationStatus = document.getElementById('location-status');
    const detailEditButton = document.getElementById('detail-edit-entry');
    const detailDeleteButton = document.getElementById('detail-delete-entry');
    const deleteModal = document.getElementById('entry-delete-modal');
    const deleteDialog = document.getElementById('entry-delete-dialog');
    const deleteCopy = document.getElementById('entry-delete-copy');
    const deleteStatus = document.getElementById('entry-delete-status');
    const deleteError = document.getElementById('entry-delete-error');
    const deleteCancel = document.getElementById('cancel-entry-delete');
    const deleteConfirm = document.getElementById('confirm-entry-delete');

    let mode = 'create';
    let selectedEntry = null;
    let editingEntry = null;
    let deletingEntry = null;
    let interactionGeneration = 0;
    let pending = false;
    let locationRepinned = false;
    let deleteReturnFocus = null;

    function clearFormFeedback() {
        formStatus.textContent = '';
        formError.textContent = '';
    }

    function setFormError(message = '') {
        formError.textContent = message;
        formStatus.textContent = '';
    }

    function setFormStatus(message = '') {
        formStatus.textContent = message;
        formError.textContent = '';
    }

    function setPhotoChoice(choice) {
        const radio = form.querySelector(`input[name="entry_photo_choice"][value="${choice}"]`);
        if (radio) radio.checked = true;
        const replacing = choice === 'replace';
        imageInputWrap.hidden = mode === 'edit' && !replacing;
        imageLabel.textContent = mode === 'edit' ? 'Upload replacement photo' : 'Upload photo (optional)';
        if (!replacing && mode === 'edit') imageInput.value = '';
    }

    function renderPhotoState() {
        if (mode !== 'edit' || !editingEntry) {
            currentPhotoState.hidden = true;
            editPhotoOptions.hidden = true;
            photoRemoveOption.hidden = false;
            imageInputWrap.hidden = false;
            imageLabel.textContent = 'Upload photo (optional)';
            return;
        }
        const hasCurrentPhoto = Boolean(editingEntry.image_path);
        currentPhotoState.hidden = false;
        currentPhotoState.textContent = hasCurrentPhoto
            ? 'This entry currently has a photo.'
            : 'This entry currently has no photo.';
        editPhotoOptions.hidden = false;
        photoKeepLabel.textContent = hasCurrentPhoto ? 'Keep current photo' : 'No photo';
        photoRemoveOption.hidden = !hasCurrentPhoto;
        setPhotoChoice('keep');
    }

    function setPending(nextPending, kind = mode) {
        pending = Boolean(nextPending);
        form.querySelectorAll('button, input, select').forEach(control => {
            control.disabled = pending;
        });
        detailEditButton.disabled = pending;
        detailDeleteButton.disabled = pending;
        deleteConfirm.disabled = pending;
        deleteCancel.disabled = pending;
        deleteCancel.hidden = pending;

        if (kind === 'delete') {
            deleteConfirm.textContent = pending ? 'DELETING...' : 'DELETE PERMANENTLY';
            deleteStatus.textContent = pending ? 'Deleting entry...' : '';
            if (pending) deleteDialog.focus();
        } else if (mode === 'edit') {
            submitButton.textContent = pending ? 'SAVING...' : 'SAVE CHANGES';
            setFormStatus(pending ? 'Saving changes...' : '');
        } else {
            submitButton.textContent = pending ? 'SENDING...' : 'SEND ENTRY';
            setFormStatus(pending ? 'Sending entry...' : '');
        }
    }

    function closeDeleteDialog({ restoreFocus = false, invalidate = false } = {}) {
        if (pending) return false;
        if (invalidate) interactionGeneration += 1;
        deleteModal.hidden = true;
        document.body.classList.remove('entry-delete-open');
        deletingEntry = null;
        deleteStatus.textContent = '';
        deleteError.textContent = '';
        if (restoreFocus && deleteReturnFocus?.isConnected && !deleteReturnFocus.disabled) {
            deleteReturnFocus.focus();
        }
        deleteReturnFocus = null;
        return true;
    }

    function resetToCreate({ message = '', increment = true } = {}) {
        if (increment) interactionGeneration += 1;
        pending = false;
        mode = 'create';
        selectedEntry = null;
        editingEntry = null;
        deletingEntry = null;
        locationRepinned = false;
        form.reset();
        latitudeInput.value = '';
        longitudeInput.value = '';
        form.classList.remove('is-editing');
        formFields.hidden = false;
        createSuccess.hidden = true;
        formTitle.textContent = 'Log a Drink';
        formContext.hidden = true;
        formContext.textContent = '';
        cancelEditButton.hidden = true;
        deleteModal.hidden = true;
        document.body.classList.remove('entry-delete-open');
        deleteReturnFocus = null;
        deleteStatus.textContent = '';
        deleteError.textContent = '';
        locationStatus.textContent = 'Waiting for GPS...';
        locationStatus.style.color = '';
        ui.updateFormToggles();
        renderPhotoState();
        setPending(false, 'create');
        if (message) setFormStatus(message);
        else clearFormFeedback();
    }

    function normalizeForm() {
        const drinkType = selectedValue(drinkTypeSelect, customDrinkType, 'Other');
        const quantity = selectedValue(quantitySelect, customQuantity, 'custom');
        if (!drinkType || !quantity) return { ok: false, message: 'Complete all fields.' };

        const formData = new FormData(form);
        formData.delete('entry_photo_choice');
        formData.delete('username');
        formData.delete('client_timestamp');
        formData.delete('client_timezone');
        formData.delete('client_timezone_code');
        formData.delete('photo_action');
        formData.set('drink_type', drinkType);
        formData.set('quantity', quantity);

        if (mode === 'create') {
            if (!latitudeInput.value || !longitudeInput.value) {
                return { ok: false, message: 'Pin location first.' };
            }
            formData.set('client_timestamp', ui.getLocalTimestamp());
            formData.set('client_timezone', Intl.DateTimeFormat().resolvedOptions().timeZone || '');
            formData.set('client_timezone_code', ui.getLocalTimeZoneCode());
            return { ok: true, formData };
        }

        if (locationRepinned) {
            if (!latitudeInput.value || !longitudeInput.value) {
                return { ok: false, message: 'Pin location first.' };
            }
            formData.set('latitude', latitudeInput.value);
            formData.set('longitude', longitudeInput.value);
            formData.set('client_timezone', Intl.DateTimeFormat().resolvedOptions().timeZone || '');
            formData.set('client_timezone_code', ui.getLocalTimeZoneCode());
        } else {
            formData.delete('latitude');
            formData.delete('longitude');
        }

        const photoChoice = form.querySelector('input[name="entry_photo_choice"]:checked')?.value || 'keep';
        const image = formData.get('image');
        if (photoChoice === 'replace' && !hasUpload(image)) {
            return { ok: false, message: 'Choose a replacement photo first.' };
        }
        if (photoChoice !== 'replace') formData.delete('image');
        formData.set('photo_action', photoChoice);
        return { ok: true, formData };
    }

    function renderCurrentLocationState() {
        if (mode === 'edit' && editingEntry) {
            if (locationRepinned && latitudeInput.value && longitudeInput.value) {
                locationStatus.textContent = `Ready: ${Number(latitudeInput.value).toFixed(3)}, ${Number(longitudeInput.value).toFixed(3)}`;
            } else {
                locationStatus.textContent = `Saved location: ${Number(editingEntry.latitude).toFixed(3)}, ${Number(editingEntry.longitude).toFixed(3)}`;
            }
            locationStatus.style.color = 'var(--success-color)';
            return;
        }
        if (latitudeInput.value && longitudeInput.value) {
            locationStatus.textContent = `Ready: ${Number(latitudeInput.value).toFixed(3)}, ${Number(longitudeInput.value).toFixed(3)}`;
            locationStatus.style.color = 'var(--success-color)';
            return;
        }
        locationStatus.textContent = 'Waiting for GPS...';
        locationStatus.style.color = '';
    }

    async function requestLocation({ repin = false } = {}) {
        const requestGeneration = interactionGeneration;
        const requestMode = mode;
        locationButton.disabled = true;
        const coordinates = await ui.getCurrentLocation(locationStatus);
        if (requestGeneration !== interactionGeneration || requestMode !== mode) {
            renderCurrentLocationState();
            if (!pending) locationButton.disabled = false;
            return null;
        }
        if (coordinates) {
            latitudeInput.value = coordinates.latitude;
            longitudeInput.value = coordinates.longitude;
            if (mode === 'edit' && repin) locationRepinned = true;
        }
        if (!pending) locationButton.disabled = false;
        return coordinates;
    }

    function beginEdit(entry) {
        if (!entry || !selectedEntry || Number(entry.id) !== Number(selectedEntry.id)) return false;
        interactionGeneration += 1;
        mode = 'edit';
        editingEntry = entry;
        deletingEntry = null;
        locationRepinned = false;
        form.reset();
        form.classList.add('is-editing');
        formFields.hidden = false;
        createSuccess.hidden = true;
        formTitle.textContent = 'Edit Drink';
        formContext.hidden = false;
        formContext.textContent = `Editing ${entry.drink_type}${entry.brand ? ` (${entry.brand})` : ''}. The original logged time will stay unchanged.`;
        cancelEditButton.hidden = false;
        setSelectValue(drinkTypeSelect, customDrinkType, entry.drink_type, 'Other');
        setSelectValue(quantitySelect, customQuantity, entry.quantity, 'custom');
        brandInput.value = entry.brand ?? '';
        abvInput.value = entry.abv;
        latitudeInput.value = entry.latitude;
        longitudeInput.value = entry.longitude;
        renderCurrentLocationState();
        ui.updateFormToggles();
        renderPhotoState();
        clearFormFeedback();
        submitButton.textContent = 'SAVE CHANGES';
        setTimeout(() => drinkTypeSelect.focus(), 0);
        return true;
    }

    function selectEntry(entry, canManage = false) {
        if (!entry) return;
        if (editingEntry && Number(editingEntry.id) !== Number(entry.id)) resetToCreate();
        interactionGeneration += 1;
        selectedEntry = canManage ? entry : null;
        if (!canManage) {
            editingEntry = null;
            closeDeleteDialog();
        }
        setPending(false, mode);
    }

    function clearSelectedEntry() {
        interactionGeneration += 1;
        selectedEntry = null;
        if (editingEntry || deletingEntry) resetToCreate({ increment: false });
        else closeDeleteDialog();
    }

    function openDelete(entry) {
        if (!entry || !selectedEntry || Number(entry.id) !== Number(selectedEntry.id) || pending) return false;
        interactionGeneration += 1;
        deletingEntry = entry;
        deleteReturnFocus = document.activeElement;
        deleteCopy.textContent = `${entry.drink_type}${entry.brand ? ` (${entry.brand})` : ''} will be permanently removed. This cannot be undone.`;
        deleteStatus.textContent = '';
        deleteError.textContent = '';
        deleteModal.hidden = false;
        document.body.classList.add('entry-delete-open');
        deleteCancel.hidden = false;
        deleteCancel.disabled = false;
        deleteConfirm.disabled = false;
        deleteConfirm.textContent = 'DELETE PERMANENTLY';
        deleteCancel.focus();
        return true;
    }

    function showCreateSuccess() {
        pending = false;
        formFields.hidden = true;
        createSuccess.hidden = false;
        clearFormFeedback();
        logAnotherButton.focus();
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (pending) return;
        clearFormFeedback();
        const normalized = normalizeForm();
        if (!normalized.ok) {
            setFormError(normalized.message);
            return;
        }

        const requestGeneration = interactionGeneration;
        const requestEntry = editingEntry;
        setPending(true, mode);
        let result;
        try {
            result = mode === 'edit'
                ? await onUpdate?.({ entry: requestEntry, formData: normalized.formData, interactionGeneration: requestGeneration })
                : await onCreate?.({ formData: normalized.formData, interactionGeneration: requestGeneration });
        } catch (error) {
            result = { ok: false, message: 'Connection unavailable. Please try again.' };
        }
        if (requestGeneration !== interactionGeneration || result?.stale) return;
        if (!result?.ok) {
            setPending(false, mode);
            setFormError(result?.message || 'The entry could not be saved. Please try again.');
            return;
        }

        if (mode === 'create') {
            setPending(false, 'create');
            showCreateSuccess();
            return;
        }
        resetToCreate({ message: result.message || 'Changes saved.' });
        onMutationSuccess?.('edit');
        void requestLocation();
    });

    cancelEditButton.addEventListener('click', () => {
        if (pending || !editingEntry) return;
        const cancelledEntry = editingEntry;
        resetToCreate();
        onCancelEdit?.(cancelledEntry);
    });

    logAnotherButton.addEventListener('click', () => {
        resetToCreate();
        void requestLocation();
    });

    drinkTypeSelect.addEventListener('change', () => ui.updateFormToggles({ focusCustom: true }));
    quantitySelect.addEventListener('change', () => ui.updateFormToggles({ focusCustom: true }));
    form.querySelectorAll('input[name="entry_photo_choice"]').forEach(radio => {
        radio.addEventListener('change', () => setPhotoChoice(radio.value));
    });
    locationButton.addEventListener('click', () => void requestLocation({ repin: mode === 'edit' }));

    deleteCancel.addEventListener('click', () => closeDeleteDialog({ restoreFocus: true, invalidate: true }));
    deleteModal.addEventListener('click', event => {
        if (event.target === deleteModal) closeDeleteDialog({ restoreFocus: true, invalidate: true });
    });
    deleteDialog.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !pending) {
            event.preventDefault();
            closeDeleteDialog({ restoreFocus: true, invalidate: true });
            return;
        }
        if (event.key !== 'Tab') return;
        const controls = [...deleteDialog.querySelectorAll('button:not([disabled]):not([hidden])')];
        if (!controls.length) {
            event.preventDefault();
            deleteDialog.focus();
            return;
        }
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
    deleteConfirm.addEventListener('click', async () => {
        if (pending || !deletingEntry) return;
        const requestEntry = deletingEntry;
        const requestGeneration = interactionGeneration;
        setPending(true, 'delete');
        let result;
        try {
            result = await onDelete?.({ entry: requestEntry, interactionGeneration: requestGeneration });
        } catch (error) {
            result = { ok: false, message: 'Connection unavailable. Please try again.' };
        }
        if (requestGeneration !== interactionGeneration || result?.stale) return;
        if (!result?.ok) {
            setPending(false, 'delete');
            deleteError.textContent = result?.message || 'The entry could not be deleted. Please try again.';
            return;
        }
        resetToCreate({ message: result.message || 'Entry deleted.' });
        onMutationSuccess?.('delete');
        void requestLocation();
    });

    resetToCreate({ increment: false });

    return {
        setConfig(config) {
            const currentDrinkType = selectedValue(drinkTypeSelect, customDrinkType, 'Other');
            const currentQuantity = selectedValue(quantitySelect, customQuantity, 'custom');
            ui.renderDrinkOptions(config);
            if (currentDrinkType) setSelectValue(drinkTypeSelect, customDrinkType, currentDrinkType, 'Other');
            if (currentQuantity) setSelectValue(quantitySelect, customQuantity, currentQuantity, 'custom');
            ui.updateFormToggles();
        },
        selectEntry,
        clearSelectedEntry,
        beginEdit,
        openDelete,
        requestInitialLocation() {
            if (
                mode !== 'create'
                || !createSuccess.hidden
                || pending
                || locationButton.disabled
                || (latitudeInput.value && longitudeInput.value)
            ) {
                return Promise.resolve(null);
            }
            return requestLocation();
        },
        resetForContextChange() {
            resetToCreate();
        },
        isInteractionCurrent(entryId, generation) {
            if (generation !== interactionGeneration) return false;
            const activeEntry = editingEntry || deletingEntry || selectedEntry;
            return Boolean(activeEntry && Number(activeEntry.id) === Number(entryId));
        },
        getInteractionGeneration() {
            return interactionGeneration;
        },
    };
}
