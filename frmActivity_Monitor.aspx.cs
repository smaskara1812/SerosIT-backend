using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using System.Text;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.Collections.Generic; 

public partial class Quality_And_Safety_frmActivity_Monitor : System.Web.UI.Page
{
    # region User defined variables
    //protected Common_DataRetrival _Common_DataRetrival;
    String strQuery;
    object objMonitorDt;
    protected DataSet Ds;
    string strConString = "";
    DataSet DsFetchedData = new DataSet();
    SqlDataAdapter Da;
    SqlConnection Conn;
    SqlCommand CmdSel;
    string ErrorString = "";
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    Int32 intUser_Id;
    #endregion

    protected void Page_Load(object sender, EventArgs e)
    {
        String strQryFilter = "";

        #region Add component attributes to control the events raised

        
        btnSearch.Attributes.Add("OnClick", "return false");

        ibtnActivity_Name.Attributes.Add("OnClick", "return false");
        ibtnRig.Attributes.Add("OnClick", "return false");

        //To call validate()
        btnAdd.Attributes.Add("OnClick", "return validate('ADD')");
        btnUpdate.Attributes.Add("OnClick", "return ValidateUpdate()");
        btnClear.Attributes.Add("OnClick", "return SetPostbackFlag('CLEAR')");
        //btnPrint.Attributes.Add("OnClick", "return SetPostbackFlag('PRINT')");

        ///To reject the manual input in textbox and only selection is allowed
        tbActivity_Name.Attributes.Add("OnKeyDown", "return RejectInput()");
        tbRig_Name.Attributes.Add("OnKeyDown", "return RejectInput()");

        /// Set a mask for date fields.
        /// 
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            tbActivity_Monitor_Dt.CssClass = "textbox_readonly";
            tbActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
            tbActivity_Monitor_Dt.Attributes.Add("OnKeyUp", "RejectInput()");
            tbActivity_Monitor_Dt.ReadOnly = true;
        }
        else
        {
            tbActivity_Monitor_Dt.ReadOnly = false;
            tbActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
            tbActivity_Monitor_Dt.Attributes.Remove("OnBlur");
            tbActivity_Monitor_Dt.Attributes.Add("OnKeyUp", "return DateMask(this)");
            tbActivity_Monitor_Dt.Attributes.Add("OnBlur", "return CheckDateOnBlur(this)");
        }
        //tbActivity_Compl_Dt.Attributes.Add("OnKeyUp", "return DateMask(this)");
        //tbActivity_Compl_Dt.Attributes.Add("OnBlur", "return CheckDateOnBlur(this)");
        tbNextActivity_Monitor_Dt.ReadOnly = false;
        tbNextActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
        tbNextActivity_Monitor_Dt.Attributes.Remove("OnBlur");
        tbNextActivity_Monitor_Dt.Attributes.Add("OnKeyUp", "return DateMask(this)");
        tbNextActivity_Monitor_Dt.Attributes.Add("OnBlur", "return CheckDateOnBlur(this)");

        #endregion

        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        var list = new List<Button>();
        list.Add(btnAdd);
        list.Add(btnUpdate);
        list.Add(btnSearch);
        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));
        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt32(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)    {            
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString,"Add");
        }
        #endregion

        #region To enable or disable Rig textbox depending on value of location in Mst_Activity table

        if (tbPostbackFlag_Hidden.Value == "ACTIVITY")
        {
            DsFetchedData = (DataSet)Session["DsHelpData"];
            string strLocation = DsFetchedData.Tables[0].Rows[0]["Activity_Location"].ToString();
            Activity_Validity_Days_Hidden.Value = Convert.ToString(DsFetchedData.Tables[0].Rows[0]["Activity_Validity_Days"]);

            if (strLocation == "R" || strLocation == "V")
            {
                ibtnRig.Visible = true;
                tbActivity_Location_Hidden.Value = "V";
            }
            else
            {
                Page.RegisterStartupScript("starScript", "<script language=JavaScript>document.getElementById('imgfieldRig').style.display = 'none';</script>");
                ibtnRig.Visible = false;
                tbRig_Name.Text = "";
                tbActivity_Location_Hidden.Value = "O";
            }
        }

        #region To calculate schedule date and assiging value to control

        if ((tbPostbackFlag_Hidden.Value == "ACTIVITY") || (tbPostbackFlag_Hidden.Value == "RIG"))
        {
            if (tbActivity_Id_Hidden.Value != "")
            {
                strQryFilter = " And Activity_Id= " + Convert.ToInt32(tbActivity_Id_Hidden.Value);
            }

            if (tbRig_Id_Hidden.Value != "")
            {
                strQryFilter += " And Rig_Id= " + Convert.ToByte(tbRig_Id_Hidden.Value);
            }
            if (Convert.ToString(Activity_Validity_Days_Hidden.Value) == "365")
            {
                strQuery = "YEAR,1";// ,MAX(Activity_Monitor_Dt)), 103)  from Activity_Monitor Where 1 = 1 " + strQryFilter;
            }
            else
            {
                strQuery = "day," + Convert.ToInt32(Activity_Validity_Days_Hidden.Value);// +" ,MAX(Activity_Monitor_Dt)), 103)  from Activity_Monitor Where 1 = 1 " + strQryFilter;
            }
            strQuery = "Select convert(char(10), DATEADD(" + strQuery + " ,MAX(Activity_Monitor_Dt)), 103)  from " + OI.Def + @"Activity_Monitor Where 1 = 1 " + strQryFilter;
            Conn = new SqlConnection(strConString);

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            CmdSel = new SqlCommand(strQuery, Conn);
            objMonitorDt = CmdSel.ExecuteScalar();


            if (tbActivity_Location_Hidden.Value == "O")
            {
                tbActivity_Monitor_Dt.Text = Convert.ToString(objMonitorDt);
                if (CheckForPreviousCompleteDt() == false)
                {
                    return;
                }
            }
            else
            {
                if (!string.IsNullOrEmpty(tbRig_Id_Hidden.Value))
                {
                    if (CheckForPreviousCompleteDt() == false)
                    {
                        return;
                    }
                    tbActivity_Monitor_Dt.Text = Convert.ToString(objMonitorDt);
                }
            }
            tbPostbackFlag_Hidden.Value = "";
        }
        #endregion

        #endregion

        #region Call functions to fetch column values for update

        /// Fetch values from the selected record and populate the controls.
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            ///To set the completion gap
            try
            {
                tbActivity_Compl_Dt.Attributes.Remove("onBlur");
            }
            catch
            { }
            tbActivity_Compl_Dt.Attributes.Add("onBlur", "return GetCopmepletionGap()");

            Get_Activity_Monitor_Info();
            tbPostbackFlag_Hidden.Value = "";
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");
        }

        #endregion

        ///To Set the focus by default to first mandatory field
        tbActivity_Name.Focus();
    }

    protected bool CheckForPreviousCompleteDt()
    {
        #region Local Variables
        string strQryFilter = "";
        string strQuery = "";
        Int16 intTotRecs = 0;
        #endregion

        if (tbActivity_Id_Hidden.Value != "")
        {
            strQryFilter = " And Activity_Id= " + Convert.ToInt32(tbActivity_Id_Hidden.Value);
        }

        if (tbRig_Id_Hidden.Value != "")
        {
            strQryFilter += " And Rig_Id= " + Convert.ToByte(tbRig_Id_Hidden.Value);
        }

        //strQuery = "select convert(char(10), DATEADD(day," + Convert.ToUInt32(Activity_Validity_Days_Hidden.Value) + " ,MAX(Activity_Monitor_Dt)), 103)  from Activity_Monitor Where 1 = 1 " + strQryFilter;
        Conn = new SqlConnection(strConString);

        //if (Conn.State == ConnectionState.Closed)
        //    Conn.Open();

        //CmdSel = new SqlCommand(strQuery, Conn);
        //objMonitorDt = CmdSel.ExecuteScalar();

        //if (tbActivity_Location_Hidden.Value == "O")
        ////tbActivity_Monitor_Dt.Text = Convert.ToString(objMonitorDt);
        //{ }
        //else
        //{
        //if (!string.IsNullOrEmpty(tbRig_Id_Hidden.Value))
        //{
        #region Checking whether user can select non completion dt entered record any record
        strQuery = "select COUNT(*) from " + OI.Def + @"Activity_Monitor where Activity_Compl_Dt is null " + strQryFilter;

        if (Conn.State == ConnectionState.Closed)
            Conn.Open();

        CmdSel = new SqlCommand(strQuery, Conn);
        intTotRecs = Convert.ToInt16(CmdSel.ExecuteScalar());
        if (intTotRecs > 0)
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "<script>alert('Kindly fill Completion Date for earlier record for selected Activity [" + tbActivity_Name.Text + "] / Rig [" + tbRig_Name.Text + "]');</script>");
            return false;
        }
        #endregion
        //tbActivity_Monitor_Dt.Text = Convert.ToString(objMonitorDt);
        //}
        //}
        return true;
    }

    private void InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum Type)
    {
        clsActivity_Monitor _ObjMaster = new clsActivity_Monitor(strConString);

        _ObjMaster.Activity_Id = Convert.ToInt32(tbActivity_Id_Hidden.Value);

        if (tbRig_Id_Hidden.Value != "")
            _ObjMaster.Rig_Id = Convert.ToByte(tbRig_Id_Hidden.Value);
        else
            _ObjMaster.Rig_Id = null;

        _ObjMaster.Activity_Monitor_Dt = tbActivity_Monitor_Dt.Text;

        _ObjMaster.Planning_Remark = tbPlanning_Remark.Text;

        if (tbActivity_Compl_Dt.Text != "")
            _ObjMaster.Activity_Compl_Dt = tbActivity_Compl_Dt.Text;
        else
            _ObjMaster.Activity_Compl_Dt = null;

        _ObjMaster.Completion_Remark = tbCompletion_Remark.Text;

        if (tbMonitor_Compl_Gap.Text != "")
            _ObjMaster.Monitor_Compl_Gap = Convert.ToInt32(tbMonitor_Compl_Gap.Text);
        else
            _ObjMaster.Monitor_Compl_Gap = null;


        switch (Type)
        {
            case EBS_Common.Classes.InsertUpdateData_Enum.Insert:
                {
                    _ObjMaster.Original_Monitor_Dt = null;
                    _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.InsertMe();
                    break;
                }

            case EBS_Common.Classes.InsertUpdateData_Enum.Update:
                {



                    _ObjMaster.Activity_Monitor_Id = Convert.ToInt32(tbActivity_Monitor_Id_Hidden.Value);

                    if (tbActivity_Compl_Dt.Text != "")
                    {
                        #region System will also create new record for next schedule
                        if (tbNextActivity_Monitor_Dt.Text != "")
                            _ObjMaster.NextActivity_Monitor_Dt = tbNextActivity_Monitor_Dt.Text;
                        else
                            _ObjMaster.NextActivity_Monitor_Dt = null;

                        if (tbNextPlanning_Remark.Text != "")
                            _ObjMaster.NextPlanning_Remark = tbNextPlanning_Remark.Text;
                        else
                            _ObjMaster.NextPlanning_Remark = null;
                        _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                        #endregion
                    }

                    Boolean IsChange_Activity_Monitor_Dt = CheckActivity_Monitor_Dt_Change_For_First_Time();

                    if (IsChange_Activity_Monitor_Dt == true)
                    {
                        _ObjMaster.Original_Monitor_Dt = tbPrev_Activity_Monitor_Dt_Hidden.Value;
                    }
                    else
                    {
                        _ObjMaster.Original_Monitor_Dt = null;
                    }

                    _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.UpdateMe();
                    break;
                }
        }
        if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", _ObjMaster.ErrorString);
            return;
        }
        ClearMe(true);
    }

    /// <summary>
    /// To clear the text boxes, default selection of combos.
    /// </summary>
    /// <param name="blnClearMainId">Whether to clear Main Id.</param>
    private void ClearMe(bool blnClearMainId)
    {
        ///To clear Hidden fields
        ///
        if (blnClearMainId == true)
        {
            tbActivity_Monitor_Id_Hidden.Value = "";
        }

        tbActivity_Id_Hidden.Value = "";
        tbRig_Id_Hidden.Value = "";
        tbActivity_Location_Hidden.Value = "";

        ///To clear Label
         

        ///To clear textboxes
        tbActivity_Name.Text = "";
        tbRig_Name.Text = "";
        tbActivity_Monitor_Dt.Text = "";
        tbPlanning_Remark.Text = "";
        tbActivity_Compl_Dt.Text = "";
        tbCompletion_Remark.Text = "";
        tbMonitor_Compl_Gap.Text = "";
        
        lblOriginal_Monitor_Dt.Visible = false;
        tbOriginal_Monitor_Dt.Visible = false;
        tbOriginal_Monitor_Dt.Text = "";

        /// Set Attributes and Reset CSSClass.
        /// 

        tbActivity_Name.Attributes.Remove("OnKeyDown");
        tbRig_Name.Attributes.Remove("OnKeyDown");
        tbPlanning_Remark.CssClass = "textbox";
        tbPlanning_Remark.Attributes.Remove("OnKeyDown");
        //tbActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
        tbActivity_Monitor_Dt.CssClass = "textbox";
        tbActivity_Compl_Dt.CssClass = "textbox";
        tbCompletion_Remark.CssClass = "textbox";
        tbPlanning_Remark.CssClass = "textbox";

        //tbActivity_Monitor_Dt.Attributes.Remove("OnBlur");
        tbActivity_Monitor_Dt.ReadOnly = false;
        tbPlanning_Remark.ReadOnly = false;
        //tbActivity_Compl_Dt.ReadOnly = true;
        //tbCompletion_Remark.ReadOnly = true;

        tbNextActivity_Monitor_Dt.Text = "";
        tbNextPlanning_Remark.Text = "";
        tbNextActivity_Monitor_Dt.CssClass = "textbox";

        ibtnRig.Visible = true;
        ibtnActivity_Name.Visible = true;

        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }

    protected void btnAdd_Click(object sender, EventArgs e)
    {
        if (CheckForPreviousCompleteDt() == false)
        {
            return;
        }

        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Insert);
    }

    protected void Get_Activity_Monitor_Info()
    {
        ClearMe(false);
        Conn = new SqlConnection(strConString);

        try
        {
            #region Get the column values from table schema.Activity_Monitor.

            string strSql = @"Select m.Activity_Id, 
                            Rig_Id, " + OI.Def + @"Fnc_Get_Col_Value('" + OI.Def + @"Mst_Rig', Rig_Id,'NAME') [Rig], convert(char(10), 
                            Activity_Monitor_Dt, 103) [Monitor_Dt], Planning_Remark,  convert(char(10), 
                            Activity_Compl_Dt, 103) [Compl_Dt], Completion_Remark, Monitor_Compl_Gap,  
                            case a.Activity_Validity_Days when 365 then 
                                    convert(char(10),  DATEADD(YEAR,1, Activity_Monitor_Dt), 103)
                                else 
								    case a.Activity_Validity_Days % 30
								    when 0 then 
									    convert(char(10),  DATEADD(MONTH,a.Activity_Validity_Days / 30, Activity_Monitor_Dt), 103)
								    else 
									    convert(char(10),  DATEADD(day,a.Activity_Validity_Days, Activity_Monitor_Dt), 103)
								    end 
                                end 
                            [Next_Monitor_Dt]  , a.Activity_Name Activity ,
                            convert(char(10), m.Original_Monitor_Dt, 103) [Original_Monitor_Dt]
     
                        From "
                            + OI.Def + @"Activity_Monitor m, " + OI.Glo + @"Mst_Activity a	                        
                        Where                       
                        a.Activity_Id= m.Activity_Id 
                        and m.Activity_Monitor_Id = @Activity_Monitor_Id ";

            Ds = new DataSet();
            Da = new SqlDataAdapter(strSql, Conn);
            Da.SelectCommand.Parameters.Add("Activity_Monitor_Id", SqlDbType.SmallInt).Value = Convert.ToInt32(tbActivity_Monitor_Id_Hidden.Value);

            Da.Fill(Ds, "Activity_Monitor");

            /// Set field values to the input controls.

            tbActivity_Id_Hidden.Value = Ds.Tables["Activity_Monitor"].Rows[0]["Activity_Id"].ToString();
            tbRig_Id_Hidden.Value = Ds.Tables["Activity_Monitor"].Rows[0]["Rig_Id"].ToString();
            tbRig_Name.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Rig"].ToString();
            tbActivity_Name.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Activity"].ToString();

            ///To Calculate Schedule date

            tbNextActivity_Monitor_Dt.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Next_Monitor_Dt"].ToString();

            tbActivity_Monitor_Dt.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Monitor_Dt"].ToString();
            tbPrev_Activity_Monitor_Dt_Hidden.Value = Ds.Tables["Activity_Monitor"].Rows[0]["Monitor_Dt"].ToString();

            tbPlanning_Remark.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Planning_Remark"].ToString();
            //tbPlanning_Remark.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Planning_Remark"].ToString();
            tbActivity_Compl_Dt.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Compl_Dt"].ToString();
            tbCompletion_Remark.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Completion_Remark"].ToString();

            if (Ds.Tables["Activity_Monitor"].Rows[0]["Original_Monitor_Dt"].ToString() != "")
            {

                if (Ds.Tables["Activity_Monitor"].Rows[0]["Monitor_Dt"].ToString() == Ds.Tables["Activity_Monitor"].Rows[0]["Original_Monitor_Dt"].ToString())
                {
                    lblOriginal_Monitor_Dt.Visible = false;
                    tbOriginal_Monitor_Dt.Visible = false;
                    tbOriginal_Monitor_Dt.Text = "";
                }
                else
                {
                    lblOriginal_Monitor_Dt.Visible = true;
                    tbOriginal_Monitor_Dt.Visible = true;
                    tbOriginal_Monitor_Dt.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Original_Monitor_Dt"].ToString();
                }

            }

            ///If competion date already exists in table then user should not be allowed to update the record  
            if (String.IsNullOrEmpty(tbActivity_Compl_Dt.Text))
            {
                tb_Compl_Dt_Exists_Hidden.Value = "N";

                tbActivity_Compl_Dt.Attributes.Remove("OnKeyUp");
                //tbActivity_Compl_Dt.Attributes.Remove("OnBlur");

                tbActivity_Compl_Dt.ReadOnly = false;
                tbActivity_Compl_Dt.ReadOnly = false;
                tbCompletion_Remark.ReadOnly = false;
                tbPlanning_Remark.ReadOnly = false;

                tbActivity_Compl_Dt.Attributes.Add("OnKeyUp", "return DateMask(this)");
                //tbActivity_Compl_Dt.Attributes.Add("OnBlur", "return CheckDateOnBlur(this)");

                tbActivity_Compl_Dt.CssClass = "textbox";
                tbCompletion_Remark.CssClass = "textbox";
                tbPlanning_Remark.CssClass = "textbox";

                tbNextActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
                tbNextActivity_Monitor_Dt.ReadOnly = false;
                tbNextActivity_Monitor_Dt.Attributes.Add("OnKeyUp", "return DateMask(this)");
                tbNextPlanning_Remark.ReadOnly = false;
                tbNextActivity_Monitor_Dt.CssClass = "textbox";
                tbNextPlanning_Remark.CssClass = "textbox";

            }
            else
            {
                tb_Compl_Dt_Exists_Hidden.Value = "Y";
                tbActivity_Compl_Dt.ReadOnly = true;
                tbCompletion_Remark.ReadOnly = true;
                tbPlanning_Remark.ReadOnly = true;


                tbActivity_Compl_Dt.CssClass = "textbox_readonly";
                tbCompletion_Remark.CssClass = "textbox_readonly";
                tbPlanning_Remark.CssClass = "textbox_readonly";


                tbActivity_Compl_Dt.Attributes.Remove("OnKeyUp");
                tbActivity_Compl_Dt.Attributes.Add("OnKeyUp", "RejectInput()");

                tbNextActivity_Monitor_Dt.ReadOnly = true;
                tbNextPlanning_Remark.ReadOnly = true;
                tbNextActivity_Monitor_Dt.CssClass = "textbox_readonly";
                tbNextPlanning_Remark.CssClass = "textbox_readonly";
                tbNextActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
                tbNextActivity_Monitor_Dt.Attributes.Add("OnKeyUp", "RejectInput()");

                tbActivity_Monitor_Dt.CssClass = "textbox_readonly";
                tbActivity_Monitor_Dt.Attributes.Remove("OnKeyUp");
                tbActivity_Monitor_Dt.Attributes.Add("OnKeyUp", "RejectInput()");

            }

            tbMonitor_Compl_Gap.Text = Ds.Tables["Activity_Monitor"].Rows[0]["Monitor_Compl_Gap"].ToString();

            /// Set Attributs of textboxes to readonly.
            tbRig_Name.CssClass = "textbox_readonly";
            tbRig_Name.Attributes.Add("OnKeyDown", "return RejectInput()");

            //tbPlanning_Remark.CssClass = "textbox_readonly";
            //tbPlanning_Remark.Attributes.Add("OnKeyDown", "return RejectInput()");

            tbMonitor_Compl_Gap.CssClass = "textbox_readonly";
            tbMonitor_Compl_Gap.Attributes.Add("OnKeyDown", "return RejectInput()");


            ///Disable the search image button.
            ibtnActivity_Name.Visible = false;
            ibtnRig.Visible = false;
            Page.RegisterStartupScript("starScript", "<script language=JavaScript>document.getElementById('imgfieldRig').style.display = 'none';</script>");
               
            #endregion
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }
        }
    }

    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    }

    protected void btnUpdate_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Update);
    }

    //    protected void tbActivity_Monitor_Dt_TextChanged(object sender, EventArgs e)
    //    {
    //        if (tbActivity_Monitor_Dt.Text != "" && tbActivity_Monitor_Id_Hidden.Value != "")
    //            Get_Next_Monitor_Dt();
    //    }


    //    protected void Get_Next_Monitor_Dt()
    //    {
    //        int intActivity_Validity_Days;
    //        Conn = new SqlConnection(strConString);

    //        try
    //        {
    //            #region Get the column values from table dbo.Mst_Activity.

    //            string strSql = @"Select a.Activity_Validity_Days
    //                        From "
    //                            + OI.Def + @"Activity_Monitor m, " + OI.Glo + @"Mst_Activity a	                        
    //                        Where                       
    //                        a.Activity_Id= m.Activity_Id 
    //                        and m.Activity_Monitor_Id = @Activity_Monitor_Id ";

    //            Ds = new DataSet();
    //            Da = new SqlDataAdapter(strSql, Conn);
    //            Da.SelectCommand.Parameters.Add("Activity_Monitor_Id", SqlDbType.SmallInt).Value = Convert.ToInt32(tbActivity_Monitor_Id_Hidden.Value);

    //            Da.Fill(Ds, "Activity_Monitor");

    //            intActivity_Validity_Days = Convert.ToInt16(Ds.Tables["Activity_Monitor"].Rows[0]["Activity_Validity_Days"].ToString());
    //            int intModvalue = (intActivity_Validity_Days % 30);
    //            DateTime dtNext_Monitor_Date = Convert.ToDateTime(tbActivity_Monitor_Dt.Text);

    //            if (intActivity_Validity_Days == 365)
    //                dtNext_Monitor_Date = dtNext_Monitor_Date.AddYears(1);
    //            else 
    //                if (intModvalue == 0)
    //                    dtNext_Monitor_Date = dtNext_Monitor_Date.AddMonths(intActivity_Validity_Days/30);
    //                else 
    //                  dtNext_Monitor_Date = dtNext_Monitor_Date.AddDays(intActivity_Validity_Days);

    //             tbNextActivity_Monitor_Dt.Text = dtNext_Monitor_Date.ToString("dd/MM/yyyy");

    //            #endregion
    //        }
    //        catch (SqlException sqlexep)
    //        {
    //            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
    //            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
    //            return;
    //        }
    //        catch (Exception exep)
    //        {
    //            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
    //            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
    //            return;
    //        }
    //        finally
    //        {
    //            if (Conn.State == ConnectionState.Open)
    //            {
    //                Conn.Close();
    //                // Conn.Dispose();
    //            }
    //        }
    //    }

    protected bool CheckActivity_Monitor_Dt_Change_For_First_Time()
    {
        string strOriginal_Monitor_Dt;
        Conn = new SqlConnection(strConString);

        try
        {
            #region Get the column values from table schema.Activity_Monitor

            string strSql = @"Select
                            convert(char(10), Original_Monitor_Dt, 103) [Original_Monitor_Dt] 
                        From "
                            + OI.Def + @"Activity_Monitor                          
                        Where                       
                         Activity_Monitor_Id = @Activity_Monitor_Id ";

            Ds = new DataSet();
            Da = new SqlDataAdapter(strSql, Conn);
            Da.SelectCommand.Parameters.Add("Activity_Monitor_Id", SqlDbType.SmallInt).Value = Convert.ToInt32(tbActivity_Monitor_Id_Hidden.Value);

            Da.Fill(Ds, "Activity_Monitor");

            /// Set field values to the input controls.

            strOriginal_Monitor_Dt = Ds.Tables["Activity_Monitor"].Rows[0]["Original_Monitor_Dt"].ToString();

            // If orginal Monitor Date is null ie updating first time Activity_Monitor_Dt and check Activity_Monitor_Dt change in UI 
            if ((String.IsNullOrEmpty(strOriginal_Monitor_Dt)) && (tbActivity_Monitor_Dt.Text != tbPrev_Activity_Monitor_Dt_Hidden.Value))
                return true;
            else
                return false;

            #endregion
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return false;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return false;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }
        }


    }

    #region COMMENTED: Ajax Popup Extender Control functionality.
    /*
    [System.Web.Services.WebMethodAttribute(), System.Web.Script.Services.ScriptMethodAttribute()]
    public static string GetDynamicContent(string contextKey)
    {        
        StringBuilder sTemp = new StringBuilder();
        string strSql = @"Select "
	                            + OI.Def + @"Fnc_Get_Col_Value('" + OI.Glo + @"Mst_Activity', Activity_Id, 'NAME') [Activity],
	                            CONVERT(varchar(10), Activity_Monitor_Dt, 103) [Activity Monitor Date],
                                DATEDIFF(DAY, Activity_Monitor_Dt, GETDATE()) [Days Overdue]
                            From " + OI.Def + @"Activity_Monitor 
                            Where Activity_Compl_Dt is null 
                            And Activity_Monitor_Dt < GETDATE()
                            Order by Activity_Monitor_Dt ";

        DataSet Ds = new DataSet();
        string strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();
        SqlConnection Conn = new SqlConnection(strConString);
        SqlDataAdapter Da = new SqlDataAdapter(strSql, Conn);
        Da.Fill(Ds, "ACTIVITIES");

        sTemp.Append("<table class='table_popup'>");
        sTemp.Append("<tr><td class='td_popup_hdr1' colspan='3'>Pending Activities</td></tr>");
        sTemp.Append("<tr>");
        sTemp.Append("<td class='td_popup_hdr2'>Activity</td>");
        sTemp.Append("<td class='td_popup_hdr2'>Scheduled Dt</td>");
        sTemp.Append("<td class='td_popup_hdr2'>Days Overdue</td>");
        sTemp.Append("</tr>");
        

        for (int i = 0; i < Ds.Tables["ACTIVITIES"].Rows.Count; i++)
        {
            sTemp.Append("<tr>");
            sTemp.Append("<td class='td_popup'>" + Ds.Tables["ACTIVITIES"].Rows[i]["Activity"].ToString() + "</td>");
            sTemp.Append("<td class='td_popup'>" + Ds.Tables["ACTIVITIES"].Rows[i]["Activity Monitor Date"].ToString() + "</td>");
            sTemp.Append("<td class='td_popup'>" + Ds.Tables["ACTIVITIES"].Rows[i]["Days Overdue"].ToString() + "</td>");
            sTemp.Append("</tr>");
        }

        sTemp.Append("</table>");

        return sTemp.ToString();        
    }
*/
    #endregion

}
