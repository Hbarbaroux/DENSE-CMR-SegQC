function update_workspace_corrected(corrected_names, corrected_seqindex, in_file, out_file)

    % Loading all data fields in case we need to save the data into
    % a completely new file
    data = load(in_file, '-mat');
    roi = data.roi;
    % Unnest multidimensional cell array into array of lists
    corrected_seqindex_unested = cellfun( @(x) cell2mat(x), corrected_seqindex, 'UniformOutput', false);
    % Add entry to the 'roi' struct with the corrected seqindex and names
    [roi.CorrectedNames] = corrected_names{:};
    [roi.CorrectedSeqIndex] = corrected_seqindex_unested{:};

    % No need to save the entire structure if file already exists
    try
        save(out_file, 'roi', '-append')
    catch
        save(out_file, '-struct', 'data')
        save(out_file, 'roi', '-append')
    end

end