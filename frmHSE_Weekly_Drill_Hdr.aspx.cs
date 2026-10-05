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
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.Collections.Generic;

public partial class Drills_frmHSE_Weekly_Drill_Hdr : System.Web.UI.Page
{
    # region User defined variables
    public DataTable Dt_Training_Grp_Dtl = new DataTable();
    //protected Common_DataRetrival _Common_DataRetrival;
    string strConString = "";
    protected DataSet Ds;
    string strSql = "";
    string ErrorString = "";
    SqlConnection Conn;
    SqlDataAdapter Da;
    Button[] btnEnableDisable;
    Int16 intMenu_id = 0;
    Int16 intUser_Id;
    #endregion

    protected void Page_Load(object sender, EventArgs e)
    {
        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        var list = new List<Button>();
        list.Add(btnAdd);
        //list.Add(btnUpdate);
        list.Add(btnSearch);
        list.Add(btnDelete);
        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));
        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt16(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)
        {

            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Add");
            tbRig_Name.Focus();
        }
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            GetDataForEdit();
            tbPostbackFlag_Hidden.Value = "";
        }
        else if (tbPostbackFlag_Hidden.Value == "GET_LAST_DRILL_CONDUCTED_DATE")//"MST_HSE_DRILL")
        {
            Get_Drill_Last_Conducted_Dt();
        }

        else if (tbPostbackFlag_Hidden.Value == "YEAR" || tbPostbackFlag_Hidden.Value == "RIG")
        {
            Get_Weeks();
        }

        #endregion
    }
    protected void Get_Weeks()
     
    {

        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            #region Get Offboard_Crew
            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Weekly_Drill_Hdr", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;
            Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.VarChar).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("Drill_Year", System.Data.SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact("01/01/" + tbDrill_Year.Text, "dd/MM/yyyy", null));
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Get_Rigs_Year_Week_Number";
            Da.Fill(Ds, "Get_Weeks");

            ///Fill the Crew Change Date dropdown 
            if (Ds.Tables["Get_Weeks"].Rows.Count > 0)
            {
                tbDrill_Week.Text = Ds.Tables["Get_Weeks"].Rows[0]["Drill_Week"].ToString();
            } 
            //tbDrill_Week.CssClass = "textbox_readonly";
            //tbDrill_Week.Attributes.Add("OnKeyDown", "return RejectInput()");
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
            }

        }
    }
    
  


    private void Get_Drill_Last_Conducted_Dt()
    {

        Conn = new SqlConnection(strConString);
        Ds = new DataSet();

        try
        {

            (grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt") as TextBox).Text = "";

            TextBox txtNewDrill_Conducted_Dt = (grdContact.FooterRow.FindControl("txtNewDrill_Conducted_Dt") as TextBox);

            if (Conn.State == ConnectionState.Closed)
            {
                Conn.Open();
            }

            //When EOSL user is selected then category MUST BE AUTOPOPULATED...
            #region To fetch values from table and assign it to controls
            string strHSE_Drill_Id = (grdContact.FooterRow.FindControl("tbHSE_Drill_Id_Hidden") as HtmlInputHidden).Value;

 
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Weekly_Drill_Hdr", Conn);
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@HSE_Drill_Id", SqlDbType.TinyInt).Value = Convert.ToByte(strHSE_Drill_Id);
            Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.TinyInt).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Drill_Conducted_Dt", SqlDbType.Date).Value =   Convert.ToDateTime(DateTime.ParseExact(txtNewDrill_Conducted_Dt.Text, "dd/MM/yyyy", null));
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Get_Drill_Last_Conducted_Dt";

            Da.Fill(Ds, "Drill_Last_Conducted");

            if (Ds.Tables["Drill_Last_Conducted"].Rows[0]["First_Time_Entry"].ToString() == "Y")
            {
                //First time enter
                (grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt") as TextBox).CssClass = "textbox";
                (grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt") as TextBox).Attributes.Remove("OnKeyDown");
            }
            else
            {
                //take from database
                (grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt") as TextBox).CssClass = "textbox_readonly";
                (grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt") as TextBox).Attributes.Add("OnKeyDown", "return RejectInput()");
                (grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt") as TextBox).Text = Ds.Tables["Drill_Last_Conducted"].Rows[0]["Drill_Conducted_Dt"].ToString();
            }
            grdContact.FooterRow.FindControl("txtNewDrill_Conducted_Dt").Focus();
          
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
            if (Conn.State != ConnectionState.Closed)
                Conn.Close();
            Conn.Dispose();
        }
    }


    protected void btnDelete_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Delete);
  
    }
    protected void btnUpdate_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Update);
    }
    protected void btnAdd_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Insert);
    }


    private void InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum Type)
    {
        clsHSE_Weekly_Drill_Hdr _ObjMaster = new clsHSE_Weekly_Drill_Hdr(strConString);          

       
        switch (Type)
        {
            case EBS_Common.Classes.InsertUpdateData_Enum.Insert:
                {
                    _ObjMaster.Rig_Id = Convert.ToInt16(tbRig_Id_Hidden.Value);
                    _ObjMaster.Drill_Year = "01/01/" + tbDrill_Year.Text;
                    _ObjMaster.Drill_Week = Convert.ToByte(tbDrill_Week.Text);
                    _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.InsertMe();
                    break;
                }
            case EBS_Common.Classes.InsertUpdateData_Enum.Update:
                {
                    //No UPDATE IS provided ...
                    //As DETAIL is dependent on HDR data..
                    break;
                }

            case EBS_Common.Classes.InsertUpdateData_Enum.Delete:
                {
                    _ObjMaster.HSE_Weekly_Drill_Hdr_Id= Convert.ToInt16(tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value);                   
                    _ObjMaster.DeleteMe();
                    break;
                }
        }
        if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", _ObjMaster.ErrorString);
            return;
        }
        string strHSE_Weekly_Drill_Hdr_Id = _ObjMaster.HSE_Weekly_Drill_Hdr_Id.ToString();


        ClearMe(true);

        //------------------------------------------------------------------------------------------------------------------------------------------------------------
        string strPopUp_Message = "";

        if (Type.ToString() == "Insert")
        {
            strPopUp_Message = "Added";
        }
        else if (Type.ToString() == "Update")
        {
            strPopUp_Message = "Updated";
        }
        else if (Type.ToString() == "Delete")
        {
            strPopUp_Message = "Deleted";
        }

        ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record " + strPopUp_Message + "', 2000,'',220);</script>", false);
        //------------------------------------------------------------------------------------------------------------------------------------------------------------

        if (tbPostbackFlag_Hidden.Value != "DELETE")
        {
            tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value = strHSE_Weekly_Drill_Hdr_Id;
            GetDataForEdit();
        }

        tbPostbackFlag_Hidden.Value = "";
    }

    protected void GetDataForEdit()
    {
        ClearMe(false);
        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");

        Conn = new SqlConnection(strConString);
        try
        { 
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Weekly_Drill_Hdr", Conn);
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;
            Da.SelectCommand.Parameters.Add("@HSE_Weekly_Drill_Hdr_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";
            Da.Fill(Ds, "DataForEdit");

            #region Set field values to the input controls.
            tbRig_Id_Hidden.Value = Ds.Tables["DataForEdit"].Rows[0]["Rig_Id"].ToString();
            tbRig_Name.Text = Ds.Tables["DataForEdit"].Rows[0]["Rig_Name"].ToString();
            tbDrill_Year.Text = Ds.Tables["DataForEdit"].Rows[0]["Drill_Year"].ToString();
            tbDrill_Week.Text = Ds.Tables["DataForEdit"].Rows[0]["Drill_Week"].ToString();
            tbStartOfWeek_Date_Hidden.Value = Ds.Tables["DataForEdit"].Rows[0]["StartOfWeek_Date"].ToString();
            tbEndOfWeek_Date_Hidden.Value = Ds.Tables["DataForEdit"].Rows[0]["EndOfWeek_Date"].ToString();

            ibtnRig_Name.Visible = false;

            tbDrill_Year.CssClass = "textbox_readonly";
            tbDrill_Year.Attributes.Add("OnKeyDown", "return RejectInput()");

            //tbDrill_Week.CssClass = "textbox_readonly";
            //tbDrill_Week.Attributes.Add("OnKeyDown", "return RejectInput()");    

            FillGrid();
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
            }
        }
    }

    public void FillGrid()
    {
        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Weekly_Drill_Dtl", Conn);
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@HSE_Weekly_Drill_Hdr_Id", SqlDbType.TinyInt).Value = Convert.ToByte(tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";

            Da.Fill(Ds, "Get_Dtl");

            DataTable contacts = Ds.Tables["Get_Dtl"];
            if (contacts.Rows.Count > 0)
            {
                grdContact.DataSource = contacts;
                grdContact.DataBind();
            }
            else
            {
                contacts.Rows.Add(contacts.NewRow());
                grdContact.DataSource = contacts;
                grdContact.DataBind();

                int TotalColumns = grdContact.Rows[0].Cells.Count;
                grdContact.Rows[0].Cells.Clear();
                grdContact.Rows[0].Cells.Add(new TableCell());
                grdContact.Rows[0].Cells[0].ColumnSpan = TotalColumns;
                grdContact.Rows[0].Cells[0].Text = "No Record Found";
            }

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
                //Conn.Dispose();
            }
        }
    }
    private void ClearMe(bool blnClearMainId)
    {
        /// Clear the hidden textboxes.
        if (blnClearMainId == true)
        {
            tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value = "";                        
        }
 
        tbRig_Name.Text = "";
        tbRig_Id_Hidden.Value = "";
        
        tbDrill_Year.Text = "";
        tbDrill_Year.CssClass = "textbox";
        tbDrill_Year.Attributes.Remove("OnKeyDown");
        
        tbDrill_Week.Text = "";
        //tbDrill_Week.CssClass = "textbox";
        //tbDrill_Week.Attributes.Remove("OnKeyDown");

        tbStartOfWeek_Date_Hidden.Value = "";
        tbEndOfWeek_Date_Hidden.Value = "";
        
        ibtnRig_Name.Visible = true;

        grdContact.DataSource = null;
        grdContact.DataBind();

        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");

    }
    protected void btnClear_Click(object sender, EventArgs e)
    { 
        ClearMe(true); 
    }

    protected void grdContact_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        if (e.CommandName.Equals("Insert"))
        {
            try
            { 

                HtmlInputHidden tbHSE_Drill_Id_Hidden = (HtmlInputHidden)grdContact.FooterRow.FindControl("tbHSE_Drill_Id_Hidden");
                TextBox txtNewDrill_Conducted_Dt= (TextBox)grdContact.FooterRow.FindControl("txtNewDrill_Conducted_Dt");
                TextBox txtNewDrill_Last_Conducted_Dt = (TextBox)grdContact.FooterRow.FindControl("txtNewDrill_Last_Conducted_Dt");
                
                TextBox txtNewRemarks = (TextBox)grdContact.FooterRow.FindControl("txtNewRemarks"); 
                 
                clsHSE_Weekly_Drill_Hdr _ObjMaster = new clsHSE_Weekly_Drill_Hdr(strConString);
                _ObjMaster.HSE_Weekly_Drill_Hdr_Id = Convert.ToInt16(tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value);
                _ObjMaster.HSE_Drill_Id = Convert.ToByte(tbHSE_Drill_Id_Hidden.Value);

                _ObjMaster.Drill_Conducted_Dt = txtNewDrill_Conducted_Dt.Text;
                _ObjMaster.Drill_Last_Conducted_Dt = txtNewDrill_Last_Conducted_Dt.Text;

                if (txtNewRemarks.Text != "")
                    _ObjMaster.Remarks = txtNewRemarks.Text;
                else
                    _ObjMaster.Remarks = null;

                _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                _ObjMaster.InsertMe_Dtl();

                if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
                {
                    throw new Exception(_ObjMaster.ErrorString);
                }
                ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record inserted', 2000,'',220);</script>", false);
    
                FillGrid();
            }


            catch (SqlException sqlexep)
            {
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Insert", sqlexep.Message.ToString());
                return;
            }
            catch (Exception exep)
            {
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Insert", exep.Message.ToString());
                return;
            }
            finally
            {
            }
        }

        if (e.CommandName == "cmdDelete")
        {

            try
            { 
                clsHSE_Weekly_Drill_Hdr _ObjMaster = new clsHSE_Weekly_Drill_Hdr(strConString);

                byte intHSE_Weekly_Drill_Dtl_Id = Convert.ToByte(e.CommandArgument);
                _ObjMaster.HSE_Weekly_Drill_Dtl_Id = intHSE_Weekly_Drill_Dtl_Id;
                _ObjMaster.DeleteMe_Dtl();


                if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
                {
                    throw new Exception(_ObjMaster.ErrorString);
                }
                ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record Deleted', 2000,'',220);</script>", false);
    
                FillGrid();

            }


            catch (SqlException sqlexep)
            {
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_delete", sqlexep.Message.ToString());
                return;
            }
            catch (Exception exep)
            {
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_delete", exep.Message.ToString());
                return;
            }
            finally
            {
            }
        }
    }


    public string getErrorScript(string strErrorMessage)
    {
        return strErrorMessage.ToString().Replace('\'', ' ').Replace('\r', ' ').Replace('\n', ' ').Replace('\"', ' ');
    }
    protected void grdContact_RowCancelingEdit(object sender, GridViewCancelEditEventArgs e)
    {
        grdContact.EditIndex = -1;
        FillGrid();
    }
    protected void grdContact_RowUpdating(object sender, GridViewUpdateEventArgs e)
    {
        try
        {
            Label lblId = (Label)grdContact.Rows[e.RowIndex].FindControl("lblId");


            TextBox txtDrill_Conducted_Dt = (TextBox)grdContact.Rows[e.RowIndex].FindControl("txtDrill_Conducted_Dt");
            TextBox txtRemarks = (TextBox)grdContact.Rows[e.RowIndex].FindControl("txtRemarks");

            clsHSE_Weekly_Drill_Hdr _ObjMaster = new clsHSE_Weekly_Drill_Hdr(strConString);
            _ObjMaster.HSE_Weekly_Drill_Dtl_Id = Convert.ToByte(lblId.Text);
            _ObjMaster.Drill_Conducted_Dt = txtDrill_Conducted_Dt.Text;
            _ObjMaster.Remarks = txtRemarks.Text;
            _ObjMaster.HSE_Weekly_Drill_Hdr_Id = Convert.ToByte(tbHSE_Weekly_Drill_Hdr_Id_Hidden.Value);
            _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
            _ObjMaster.UpdateMe_Dtl();

            if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
            {               
                throw new Exception(_ObjMaster.ErrorString);
            }

            ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record Updated', 2000,'',220);</script>", false);
    
            grdContact.EditIndex = -1;
            FillGrid();
        }
        catch (SqlException sqlexep)
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update", sqlexep.Message.ToString());
            return;
        }
        catch (Exception exep)
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update", exep.Message.ToString());
            return;
        }
        finally
        {
        }
    }
    protected void grdContact_RowEditing(object sender, GridViewEditEventArgs e)
    {
        grdContact.EditIndex = e.NewEditIndex;
        FillGrid();
    }


    protected void grdContact_RowDataBound(object sender, GridViewRowEventArgs e)
    {
        if (e.Row.RowType == DataControlRowType.Footer)
        {
            HtmlInputHidden tbHSE_Drill_Id_Hidden = (HtmlInputHidden)e.Row.FindControl("tbHSE_Drill_Id_Hidden");
            TextBox txtNewHSE_Drill_Name = (TextBox)e.Row.FindControl("txtNewHSE_Drill_Name");
             
            TextBox txtNewDrill_Conducted_Dt = (TextBox)e.Row.FindControl("txtNewDrill_Conducted_Dt");

            txtNewDrill_Conducted_Dt.Attributes.Add("onchange", "Get_Last_Drill_Conducted_Date(" + tbHSE_Drill_Id_Hidden.ClientID + "," + txtNewDrill_Conducted_Dt.ClientID + ");return false;");
                


            ImageButton ibtnNewHSE_Drill = (ImageButton)e.Row.FindControl("ibtnNewHSE_Drill");            
            ibtnNewHSE_Drill.Attributes.Add("onclick", "Show_HSE_Drills(" + tbHSE_Drill_Id_Hidden.ClientID + "," + txtNewHSE_Drill_Name.ClientID + ");return false;");
        } 
    }
    protected void grdContact_SelectedIndexChanged(object sender, EventArgs e)
    {

    }
    protected void grdContact_DataBound(object sender, EventArgs e)
    {

    }
}